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
NOTE_MAX = 200        # output tokens for a note pass
QUERY_MAX = 40
ANSWER_ROUNDS = 3

NOTE_SYSTEM = """You keep notes for a chat between a user and an assistant. Later the assistant sees only these notes, not the chat.
Read the latest exchange and write only what is new or changed, one fact per line:
ADD: <fact> | tags: <3-6 plain words someone might use to ask about it> | <date, place, money, person, rule, plan, number or other>
CHANGE <line number>: <the fact as it is now> | tags: ... | <kind>
Keep concrete details, even from side comments: names, dates, times, places, amounts, counts, rules, decisions, what was cancelled or changed.
If nothing new came up, write NONE."""

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
    return line.split(" | tags:")[0]


def render(lines):
    return "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines)) or "(no notes yet)"


def apply_ops(lines, text):
    ops = []
    for raw in text.splitlines():
        s = raw.strip().lstrip("-*• ").strip()
        m = re.match(r"^ADD\s*:\s*(.+)$", s, re.I)
        if m:
            lines.append(m.group(1).strip()); ops.append(("add", None)); continue
        m = re.match(r"^CHANGE\s*(?:line\s*)?(\d+)\s*:\s*(.+)$", s, re.I)
        if m:
            n = int(m.group(1)) - 1
            if 0 <= n < len(lines): lines[n] = m.group(2).strip(); ops.append(("change", n + 1))
            else: lines.append(m.group(2).strip()); ops.append(("change-missing-line", n + 1))
    return ops


def last_exchange(msgs):
    u = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
    a = msgs[-1]["content"] if msgs and msgs[-1]["role"] == "assistant" else ""
    first = " ".join(a.split()[:60]) + (" …" if len(a.split()) > 60 else "")
    return u, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--chats", default=""); ap.add_argument("--max-turns", type=int, default=None)
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

    def note_chat(d):
        lines, log = [], []
        msgs = d["messages"]
        users = [i for i, m in enumerate(msgs) if m["role"] == "user"]
        if a.max_turns: users = users[: a.max_turns]
        for n, i in enumerate(users):
            reply = msgs[i + 1]["content"] if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant" else "(no reply)"
            user_msg = f"NOTES:\n{render(lines)}\n\nLATEST EXCHANGE:\nUser: {msgs[i]['content']}\nAssistant: {reply}"
            prompt = wb.lfm3_prompt([{"role": "system", "content": NOTE_SYSTEM}, {"role": "user", "content": user_msg}], [], thinking=False)
            out, secs = gen(prompt, NOTE_MAX)
            ops = apply_ops(lines, out)
            log.append({"turn": n, "prompt_tokens": ntok(prompt), "out_tokens": ntok(out), "gpu_s": round(secs, 3), "out": out, "ops": ops, "lines": len(lines)})
        return lines, log

    def packets(d, lines):
        msgs, q = d["messages"], d["question"]
        u, r = last_exchange(msgs)
        recent = f"Last exchange:\nUser: {u}\nYou: {r}"
        # LFM3 writes its own query (thinking off), seeing only the last exchange and the new message
        qp = wb.lfm3_prompt([{"role": "system", "content": QUERY_SYSTEM},
                             {"role": "user", "content": f"{recent}\n\nNew message: {q}"}], [], thinking=False)
        lq, qsecs = gen(qp, QUERY_MAX)
        lq = lq.strip().splitlines()[0] if lq.strip() else q
        res = {"recent": recent, "lfm3_query": lq, "query_gpu_s": round(qsecs, 3), "query_prompt_tokens": ntok(qp), "query_out_tokens": ntok(lq)}
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
