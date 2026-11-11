"""Notes + search as Squiggle's fresh context, with LFM3 1.7B doing everything.

1. Note pass. After every exchange of the 16 context-packets chats, a separate LFM3 call with its own short prompt
   and thinking off reads the numbered notes plus that one exchange and writes only what's new or changed:
     ADD: <fact> | tags: <plain words> | <kind>      CHANGE <n>: <fact> | tags: ... | <kind>      NONE
   The harness applies the lines. Token counts are logged to estimate the time on the phone.
2. Packets. For each final question: the last exchange (user message whole, the reply's opening) plus the top note
   lines from: BM25 on the raw message (with and without the tags), bge-small embeddings, hybrid (RRF), and an
   LFM3-written search query (thinking off) into BM25 and into hybrid. Whole notes as the ceiling.
3. Answers. LFM3 with Squiggle PR 7's prompt and real engine limits (1,024-token reply, 400-token thinking budget)
   answers from a packet handed over as the result of a relevant_context call it "already made". No chat history.

  python notes_search.py OUT [--chats 1,2] [--max-turns N]
"""
import argparse, json, math, os, re, sys, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import run as wb   # experiments/whiteboard/run.py: Squiggle PR 7 prompt + LFM3 format + llama-server backend

K = 8                 # note lines per packet
NOTE_MAX = 300        # output tokens for a note pass
QUERY_MAX = 40
ANSWER_ROUNDS = 6     # agent.js: no more lookups after LITE_CHAT_NUDGE * 2

NOTE_SYSTEM = """You keep notes for a chat between a user and an assistant. Later the assistant sees only these notes, not the chat, so anything not written down is forgotten.
Read the latest exchange and write only what is NEW or CHANGED. Never repeat a fact that is already in the notes. Most exchanges add 0-2 lines.
- A new fact: one line starting with "- ", ending with a few plain words someone might use to ask about it, in brackets.
- Be extra sure to fix facts that changed. If the user corrects something, or a plan, date, number or choice changes, write "- CHANGE <its number>: " and the fact as it is now. If something no longer holds at all (cancelled, ruled out), write "- DELETE <its number>".
Example: the notes say "3. Billy's birthday: Mar 15, 2020 [billy birthday]" and the user says "oh wait no, Billy's birthday is actually Dec 16". You write:
- CHANGE 3: Billy's birthday: Dec 16, 2020 (not Mar 15) [billy birthday date]
Keep names, dates, times, places, amounts, counts, rules, decisions, even from side comments. If nothing is new or changed, write NONE."""

QUERY_SYSTEM = "Write a search query for the notes of this chat: what does the new message need looked up? Reply with only 3-8 plain keywords."

RELEVANT = {"name": "relevant_context", "description": "What Squiggle's notes from earlier in this chat say about the request, plus the last exchange.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "What to look up"}}, "required": ["query"]}}
TOOLS = wb.TOOLS + [RELEVANT]

TOK = re.compile(r"[a-z0-9][a-z0-9'-]*")
STOP = wb.STOP


def toks(s):
    return [w.rstrip(".-'") for w in TOK.findall(s.lower()) if w.rstrip(".-'") and w.rstrip(".-'") not in STOP]


def bm25_rank(docs, query):
    T = [toks(d) for d in docs]; q = toks(query)
    if not T or not q: return list(range(len(docs)))
    N, avg = len(T), sum(map(len, T)) / max(1, len(T))
    df = Counter(w for d in T for w in set(d))
    sc = []
    for i, d in enumerate(T):
        tf, s = Counter(d), 0.0
        for w in q:
            if tf[w]:
                s += math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / max(avg, 1)))
        sc.append(s)
    return sorted(range(len(docs)), key=lambda i: -sc[i])


def strip_tags(line):
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", line.split(" | tags:")[0])


def render(lines):
    # deleted lines (None) keep their number, so later CHANGE/DELETE numbers stay right, but aren't shown
    return "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines) if l is not None) or "(no notes yet)"


def live(lines):
    return [l for l in lines if l is not None]


def visible(out):
    """The answer part of an output: no <think>..</think>, no unclosed <think>, nothing before a stray </think>."""
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).split("<think>")[0]
    return out.split("</think>")[-1]


def apply_ops(lines, text):
    ops = []
    for raw in visible(text).splitlines():
        s = raw.strip()
        if not s or s.upper().startswith("NONE") or "<fact>" in s or "plain words" in s: continue
        body = re.sub(r"^[-*•]\s*", "", s)
        m = re.match(r"^CHANGE\s*(?:line\s*)?(\d+)\s*:\s*(.+)$", body, re.I)
        if m:
            n = int(m.group(1)) - 1
            if 0 <= n < len(lines): lines[n] = m.group(2).strip(); ops.append(("change", n + 1))
            else: lines.append(m.group(2).strip()); ops.append(("change-missing-line", n + 1))
            continue
        m = re.match(r"^DELETE\s*(?:line\s*)?(\d+)\b", body, re.I)
        if m:
            n = int(m.group(1)) - 1
            if 0 <= n < len(lines) and lines[n] is not None: lines[n] = None; ops.append(("delete", n + 1))
            continue
        m = re.match(r"^ADD\s*:\s*(.+)$", body, re.I)
        if m or re.match(r"^[-*•]", s):
            new = (m.group(1) if m else body).strip()
            key = norm(new)
            if any(l is not None and norm(l) == key for l in lines):   # exact repeat of a line already there
                ops.append(("repeat-skipped", None)); continue
            lines.append(new); ops.append(("add", None))
    return ops


def junk(line):
    """Lines run 3's parser let in that aren't notes: NONE, talk about the notes, cut-off lines."""
    t = strip_tags(line).strip()
    return (not t or t.upper().startswith("NONE") or re.match(r"^(add|adding|added|note|update|record|new fact|no new|nothing new)\b.*\b(fact|note|exchange|notes)\b", t, re.I)
            or t.endswith(("=", ":", ",", "(", "-")) or len(t.split()) < 2)


def near_repeat(lines, new):
    """Most of the new line's words are already in one live line (run 3 only skipped exact repeats)."""
    w = set(toks(strip_tags(new)))
    if not w: return True
    return any(l is not None and len(w & set(toks(strip_tags(l)))) / len(w) >= 0.8 for l in lines)


def apply_ops_strict(lines, text):
    ops = []
    for raw in visible(text).splitlines():
        s = raw.strip()
        body = re.sub(r"^[-*\u2022]\s*", "", s)
        if re.match(r"^(CHANGE|DELETE)\b", body, re.I):
            ops += apply_ops(lines, s); continue
        if not re.match(r"^([-*\u2022]|ADD\s*:)", s, re.I): continue
        new = re.sub(r"^ADD\s*:\s*", "", body, flags=re.I).strip()
        if junk(new): ops.append(("junk-skipped", None)); continue
        if near_repeat(lines, new): ops.append(("near-repeat-skipped", None)); continue
        lines.append(new); ops.append(("add", None))
    return ops


def norm(line):
    return re.sub(r"\W+", " ", strip_tags(line)).lower().strip()


# ── Run 4a: native LFM3 layout for the note pass ─────────────────────────────
# Only system / user / assistant / tool roles (Liquid's template has no harness role). The real exchange goes in as
# real turns; the notes come back from a read_notes call it "already made" (only lines matching the exchange, plus the
# most recently touched); its edits go out as an update_notes tool call, so its output doesn't look like its notes.
NATIVE_SYSTEM = """You keep notes for a chat between a user and an assistant. You never reply to the user: your only job is the notes. Later the assistant sees only these notes, not the chat, so anything not written down is forgotten.
After each exchange you get the saved notes that relate to it from read_notes. Then call update_notes with only what is new or changed:
- add: new facts, one short line each (names, dates, times, places, amounts, counts, rules, decisions, even from side comments). Never add a fact that read_notes already shows.
- change: when a fact changed, the note's number and the fact as it is now. Be extra sure to fix facts the user corrects. Example: note 3 says "Billy's birthday: Mar 15, 2020" and the user says "oh wait no, Billy's birthday is actually Dec 16" -> change: ["3: Billy's birthday: Dec 16, 2020 (not Mar 15)"]
- delete: numbers of notes that no longer hold at all (cancelled, ruled out).
If nothing is new or changed, don't call update_notes."""
READ_NOTES = {"name": "read_notes", "description": "Show the saved notes that relate to a query, numbered.",
              "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "What to look for"}}, "required": ["query"]}}
UPDATE_NOTES = {"name": "update_notes", "description": "Add, change or delete notes.",
                "parameters": {"type": "object", "properties": {
                    "add": {"type": "array", "items": {"type": "string"}, "description": "New facts, one short line each"},
                    "change": {"type": "array", "items": {"type": "string"}, "description": "\"<note number>: <the fact as it is now>\""},
                    "delete": {"type": "array", "items": {"type": "integer"}, "description": "Numbers of notes that no longer hold"}}}}
NATIVE_TOOLS = [READ_NOTES, UPDATE_NOTES]
MATCHED, RECENT = 8, 3


def as_list(v):
    if v is None or v == "": return []
    if isinstance(v, list): return v
    if isinstance(v, str):
        try:
            j = json.loads(v)
            return j if isinstance(j, list) else [j]
        except Exception:
            return [x.strip() for x in v.splitlines() if x.strip()]
    return [v]


def apply_native(lines, touched, calls):
    """update_notes args -> edits. Exact repeats of a live line are skipped, as in run 3."""
    ops = []
    for c in calls:
        if c["name"] != "update_notes":
            ops.append(("other-call", c["name"])); continue
        a = c["arguments"]
        for x in as_list(a.get("change")):
            m = re.match(r"^\s*#?(\d+)\s*[:.)-]\s*(.+)$", str(x), re.S)
            if isinstance(x, dict): m = None; n, txt = int(x.get("number", x.get("n", 0)) or 0), str(x.get("text", x.get("fact", "")))
            elif m: n, txt = int(m.group(1)), m.group(2).strip()
            else: ops.append(("change-unparsed", None)); continue
            if 1 <= n <= len(lines) and lines[n - 1] is not None and txt:
                lines[n - 1] = txt; touched.append(n - 1); ops.append(("change", n))
            else: ops.append(("change-missing-line", n))
        for x in as_list(a.get("delete")):
            try: n = int(str(x).strip().lstrip("#"))
            except Exception: ops.append(("delete-unparsed", None)); continue
            if 1 <= n <= len(lines) and lines[n - 1] is not None:
                lines[n - 1] = None; ops.append(("delete", n))
        for x in as_list(a.get("add")):
            txt = str(x).strip()
            if not txt: continue
            if any(l is not None and norm(l) == norm(txt) for l in lines):
                ops.append(("repeat-skipped", None)); continue
            lines.append(txt); touched.append(len(lines) - 1); ops.append(("add", None))
    return ops


def related(lines, touched, query):
    """Line numbers for read_notes: the BM25 matches for the exchange plus the most recently touched lines."""
    live_idx = [i for i, l in enumerate(lines) if l is not None]
    if not live_idx: return []
    order = bm25_rank([lines[i] for i in live_idx], query)
    picked = [live_idx[j] for j in order[:MATCHED]]
    for i in reversed(touched):
        if len([p for p in picked if p in touched[-RECENT:]]) >= RECENT: break
        if lines[i] is not None and i not in picked: picked.append(i)
        if len(picked) >= MATCHED + RECENT: break
    return sorted(set(picked))


def last_exchange(msgs):
    u = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
    a = msgs[-1]["content"] if msgs and msgs[-1]["role"] == "assistant" else ""
    first = " ".join(a.split()[:60]) + (" …" if len(a.split()) > 60 else "")
    return u, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--chats", default=""); ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--variant", default="run3", choices=["run3", "native", "strict"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    data = json.load(open("data.json"))
    if a.chats: data = [d for d in data if str(d["id"]) in a.chats.split(",")]
    t0 = time.time()
    be = wb.Llama()
    tok = be.tok
    ntok = lambda s: len(tok.encode(s, add_special_tokens=False))
    print(f"model ready in {time.time() - t0:.0f}s", flush=True)
    from sentence_transformers import SentenceTransformer
    import torch
    emb = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda" if torch.cuda.is_available() else "cpu")
    emb_lock = threading.Lock()
    shell = wb.Shell()
    print_lock = threading.Lock()

    def gen(prompt, n):
        t = time.time()
        out = be.one((prompt, n))
        return out, time.time() - t

    def gen_off(prompt, n):
        """Thinking off. LFM3 sometimes thinks anyway (its card says thinking-off is inconsistent): if it opens a
        <think> and runs out inside it, close it with Squiggle's budget note and let it write the answer."""
        out, secs = gen(prompt, n)
        if out.lstrip().startswith("<think>") and "</think>" not in out:
            kept = out + "\n" + wb.THINK_NOTE + "\n</think>\n"
            more, s2 = gen(prompt + kept, n)
            return kept + more, secs + s2, True
        return out, secs, False

    def note_chat(d):
        lines, log, touched = [], [], []
        msgs = d["messages"]
        users = [i for i, m in enumerate(msgs) if m["role"] == "user"]
        if a.max_turns: users = users[: a.max_turns]
        for n, i in enumerate(users):
            reply = msgs[i + 1]["content"] if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant" else "(no reply)"
            shown, hidden = list(lines), 0   # fit the 4K window like the phone: the oldest note lines drop out of view
            while a.variant != "native":
                user_msg = f"NOTES:\n{render(shown)}\n\nLATEST EXCHANGE:\nUser: {msgs[i]['content']}\nAssistant: {reply}"
                prompt = wb.lfm3_prompt([{"role": "system", "content": NOTE_SYSTEM}, {"role": "user", "content": user_msg}], [], thinking=False)
                if ntok(prompt) <= wb.WINDOW - NOTE_MAX or not any(l is not None for l in shown): break
                j = next(k for k, l in enumerate(shown) if l is not None); shown[j] = None; hidden += 1
            prompt = prompt if a.variant != "native" else None
            if a.variant == "native":
                q = msgs[i]["content"] + " " + " ".join(reply.split()[:60])
                shown_idx = related(lines, touched, q)
                notes_txt = "\n".join(f"{k + 1}. {lines[k]}" for k in shown_idx) or "(no notes yet)"
                conv = [{"role": "system", "content": NATIVE_SYSTEM}, {"role": "user", "content": msgs[i]["content"]}]
                if reply != "(no reply)": conv.append({"role": "assistant", "content": reply})
                conv += [{"role": "assistant", "content": "", "tool_calls": [{"name": "read_notes", "arguments": {"query": " ".join(toks(q)[:12])}}]},
                         {"role": "tool", "content": notes_txt}]
                prompt, hidden = wb.lfm3_prompt(conv, NATIVE_TOOLS, thinking=False), 0
            out, secs, forced = gen_off(prompt, NOTE_MAX)
            if a.variant == "native":
                _, said, calls = wb.parse_output(out if "</think>" in out else "</think>" + out)
                ops = apply_native(lines, touched, calls)
                if not calls and said.strip() and not said.strip().upper().startswith("NONE"): ops.append(("talked-instead", None))
            elif a.variant == "strict":
                ops = apply_ops_strict(lines, out)
            else:
                ops = apply_ops(lines, out)
            log.append({"turn": n, "hidden_lines": hidden, "prompt_tokens": ntok(prompt), "out_tokens": ntok(out), "gpu_s": round(secs, 3), "forced": forced, "out": out, "ops": ops, "lines": len(lines)})
        return lines, log

    def packets(d, lines):
        msgs, q = d["messages"], d["question"]
        u, r = last_exchange(msgs)
        recent = f"Last exchange:\nUser: {u}\nYou: {r}"
        # LFM3 writes its own query (thinking off), seeing only the last exchange and the new message
        qp = wb.lfm3_prompt([{"role": "system", "content": QUERY_SYSTEM},
                             {"role": "user", "content": f"{recent}\n\nNew message: {q}"}], [], thinking=False)
        lq_raw, qsecs, _ = gen_off(qp, QUERY_MAX)
        lq = next((l.strip() for l in visible(lq_raw).splitlines() if l.strip()), q)
        res = {"recent": recent, "lfm3_query": lq, "lfm3_query_raw": lq_raw, "query_gpu_s": round(qsecs, 3), "query_prompt_tokens": ntok(qp), "query_out_tokens": ntok(lq)}
        order = {}
        if lines:
            order["bm25"] = bm25_rank(lines, q)
            order["bm25_notags"] = bm25_rank([strip_tags(l) for l in lines], q)
            with emb_lock:
                import numpy as np
                C = emb.encode(lines, normalize_embeddings=True)
                P = "Represent this sentence for searching relevant passages: "
                Q1, Q2 = emb.encode([P + q, P + lq], normalize_embeddings=True)
            order["emb"] = sorted(range(len(lines)), key=lambda i: -float(C[i] @ Q1))
            emb_q = sorted(range(len(lines)), key=lambda i: -float(C[i] @ Q2))
            def rrf(*ranks):
                s = Counter()
                for rk in ranks:
                    for p, i in enumerate(rk): s[i] += 1 / (60 + p)
                return sorted(range(len(lines)), key=lambda i: -s[i])
            order["hybrid"] = rrf(order["bm25"], order["emb"])
            order["lfm3q_bm25"] = bm25_rank(lines, lq)
            order["lfm3q_hybrid"] = rrf(order["lfm3q_bm25"], emb_q)
        pk = {}
        for name, o in order.items():
            top = sorted(o[:K])   # keep the notes' own order inside the packet
            pk[name] = recent + "\n\nNotes:\n" + "\n".join(f"- {strip_tags(lines[i])}" for i in top)
        pk["whole"] = recent + "\n\nNotes:\n" + ("\n".join(f"- {strip_tags(l)}" for l in lines) or "(none)")
        res["packets"] = pk
        return res

    def answer(d, lines, packet, query, label):
        cid = f"ans-{label}-{d['id']}"
        notes_file = "\n".join(f"- {strip_tags(l)}" for l in lines)
        shell.run(cid, f"cat > {wb.NOTES} <<'SQUIGGLE_EOF'\n{notes_file}\nSQUIGGLE_EOF")
        head = {"role": "system", "content": wb.SYSTEM}
        tail = [{"role": "user", "content": d["question"]},
                {"role": "assistant", "content": "", "tool_calls": [{"name": "relevant_context", "arguments": {"query": query}}]},
                {"role": "tool", "content": packet}]
        trace = []
        runner = wb.Chat({"id": d["id"], "messages": [], "question": d["question"]}, "ans", shell, tok, None)
        runner.chat_id = cid
        for r in range(ANSWER_ROUNDS + 1):
            p = wb.lfm3_prompt([head] + tail, TOOLS)
            room = wb.WINDOW - ntok(p)
            out, secs = gen(p, max(64, min(wb.MAX_OUTPUT, room)))
            reasoning, text, calls = wb.parse_output(out)
            step = {"round": r, "prompt_tokens": ntok(p), "reasoning": reasoning, "text": text, "calls": calls,
                    "budget_hit": wb.THINK_NOTE in out, "gpu_s": round(secs, 3)}
            trace.append(step)
            if not calls or r == ANSWER_ROUNDS: break
            results = []
            for c in calls:
                if c["name"] in ("find", "relevant_context"):
                    qq = str(c["arguments"].get("query", ""))
                    top = sorted(bm25_rank(lines, qq)[:K]) if lines else []
                    results.append({"results": [strip_tags(lines[i]) for i in top]} if top else {"results": [], "note": "Nothing found."})
                else:
                    results.append(runner.run_tool(c, 0))
            step["results"] = results
            tail.append({"role": "assistant", "content": text, "reasoning": reasoning, "tool_calls": calls})
            for res in results: tail.append({"role": "tool", "content": wb.result_text(res)})
        return trace

    def chat(d):
        lines, log = note_chat(d)
        with print_lock: print(f"notes done chat {d['id']}: {len(lines)} lines after {len(log)} turns, {(time.time() - t0) / 60:.1f} min", flush=True)
        lines = live(lines)
        pk = packets(d, lines)
        rec = {"chat": d["id"], "notes": lines, "note_log": log, **pk, "answers": {}}
        json.dump(rec, open(os.path.join(a.out, f"chat-{d['id']}.json"), "w"), indent=1, ensure_ascii=False)
        for label, key, query in (("whole", "whole", d["question"]), ("bm25", "bm25", d["question"]),
                                  ("hybrid", "hybrid", d["question"]), ("lfm3q_bm25", "lfm3q_bm25", pk["lfm3_query"])):
            if key in pk["packets"]:
                rec["answers"][label] = answer(d, lines, pk["packets"][key], query, label)
        json.dump(rec, open(os.path.join(a.out, f"chat-{d['id']}.json"), "w"), indent=1, ensure_ascii=False)
        with print_lock: print(f"done chat {d['id']} at {(time.time() - t0) / 60:.1f} min", flush=True)

    with ThreadPoolExecutor(len(data)) as ex:
        list(ex.map(chat, data))
    print(f"all done in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
