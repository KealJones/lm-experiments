"""Whiteboard replay: LFM3 1.7B with Squiggle's PR 7 prompt keeps its own notes file through bash.

Each of the 16 context-packets chats is replayed turn by turn. Arms:
  notes   4K window. Every user turn: the model sees its last 2 exchanges, the new user message, a `cat /home/notes.md`
          it "already ran" (the notes, as its own tool result), the recorded assistant reply, then Squiggle's
          end-of-turn note asking it to update /home/notes.md. It edits the file with bash (up to 4 tool rounds).
          At the end it answers the final question from: last 2 exchanges + question + its notes.
  window  4K window, no notes: last 2 exchanges + question. find still searches the earlier turns (BM25).
  full    the whole chat + question, no 4K limit (ceiling; LFM3 takes 256K).
Everything the model sees is rendered exactly as Squiggle PR 7 renders it for LFM3 (agent.js LITE_SYSTEM_BASH +
toolNamesLine, toolformats/lfm3.js, engine-wllama.js resultText, untrusted.js wrapUntrusted).

  python run.py OUT [--chats 1,2] [--max-turns N] [--arms notes,window,full] [--backend llama|vllm|hf]
"""
import argparse, json, math, os, random, re, string, subprocess, sys, time
from collections import Counter
from datetime import datetime

MODEL = "LiquidAI/LFM3-1.7B"
WINDOW = 4096          # Squiggle's LFM3 build (engine.js maxContext)
MAX_OUTPUT = 1536      # agent.js MAX_OUTPUT
MIN_REPLY = 512        # drop the oldest window turns before the reply room goes under this
KEEP_EXCHANGES = 2
UPDATE_ROUNDS = 4
ANSWER_ROUNDS = 6      # agent.js LITE_CHAT_NUDGE * 2: no more lookups after this
NOTES = "/home/notes.md"
SAMPLING = dict(temperature=0.1, top_k=50, top_p=1.0, repetition_penalty=1.1)   # engine.js lfm3 settings

# ── Squiggle PR 7 (f987588), small-model mode on the bash surface ─────────────
LITE_SYSTEM_BASH = "\n".join([
    "You are Squiggle, an assistant that figures things out. Think first. If you",
    "don't know something, don't guess: find it or look it up. For anything with",
    "more than one step, make a plan, then do one step at a time.",
    "Use bash for files, the web, GitHub and maths: search WORDS, curl URL | grep -i WORD, git, gh, bc; `man` lists",
    "the custom commands. find(query) searches recipes, memory and past chats; need(what) asks the user for something only they know.",
    "Your context window is small: never cat a whole file or curl a whole page. Pipe into grep, head, tail, sed -n or wc,",
    "or save it to a file (> /tmp/page.txt) and work on the file in small pieces.",
    "Plan only when the request takes more than one step: plan(goal, steps), then done(result) after each step.",
])
TOOLS = [
    {"name": "remember", "description": "Save a lasting fact about the user or their projects (preferences, decisions, names, how things work). Saved as subject → relation → object.",
     "parameters": {"type": "object", "properties": {"subject": {"type": "string", "description": "Who/what, e.g. \"Keal\" or \"squiggle\""}, "relation": {"type": "string", "description": "e.g. \"prefers\", \"uses\", \"is deployed on\""}, "object": {"type": "string", "description": "the value"}, "note": {"type": "string", "description": "optional detail"}}, "required": ["subject", "relation", "object"]}},
    {"name": "bash", "description": "Run bash: pipes, cat, ls, grep, sed, awk, find, jq, the usual tools. Files: /home (yours), /repos (git clones), /web, /tmp. Custom commands: git, gh, curl, search, wiki, node, bc (`man` lists them, `<command> --help` explains one).",
     "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The command, e.g. ls /repos or grep -rn \"login\" /repos/app/src | head"}}, "required": ["command"]}},
    {"name": "plan", "description": "Plan a request that takes more than one step; you then work it one step at a time. Calling it again revises the plan.",
     "parameters": {"type": "object", "properties": {"goal": {"type": "string", "description": "What the user wants, in one line"}, "steps": {"type": "array", "items": {"type": "string"}, "description": "Short imperative steps"}}, "required": ["goal", "steps"]}},
    {"name": "need", "description": "Ask for something only the user can tell you. Squiggle searches first and asks them if it finds nothing.",
     "parameters": {"type": "object", "properties": {"what": {"type": "string", "description": "What is missing, e.g. \"which repo the site lives in\""}}, "required": ["what"]}},
    {"name": "find", "description": "Search what Squiggle knows: other tools (and how to call them), recipes from past tasks, memory, past chats, this task's results.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "What you are looking for"}}, "required": ["query"]}},
    {"name": "tool_info", "description": "Get how to call tools from the \"other tools\" list; they are ready to call after this. Ask for all you expect to need at once.",
     "parameters": {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}, "description": "Tool names from the list"}}, "required": ["names"]}},
]
TODAY = datetime.now().strftime("%a %b %d %Y")
SYSTEM = f"{LITE_SYSTEM_BASH}\nTools ready to call: {', '.join(t['name'] for t in TOOLS)}.\nToday is {TODAY}."
# The end-of-turn note (Keal: an instruction, not a new tool), in Squiggle's v3 harness-note dialect.
NUDGE = ("(Squiggle: Older turns are dropped from your view; " + NOTES + " is what you'll have instead. Update it now with "
         "anything from this exchange that might be needed later: names, dates, times, places, numbers, plans, decisions, "
         "changes, even side comments. Change lines that are out of date instead of adding a second version. Write it in "
         "your own words, as your notes. If nothing new came up, leave it as it is.)")
KEY = "".join(random.Random(7).choices(string.ascii_lowercase + string.digits, k=8))


def wrap_untrusted(source, text):
    safe = re.sub(r"<(/?)untrusted", r"‹\1untrusted", str(text), flags=re.I)
    return f'<untrusted source="{source}" key="{KEY}">\n{safe}\n</untrusted key="{KEY}">'


def result_text(resp):
    """engine-wllama.js resultText."""
    if resp is None: return ""
    if not isinstance(resp, (dict, list)): return str(resp)
    if isinstance(resp, list): return json.dumps(resp, indent=1, ensure_ascii=False)
    if not all(v is None or isinstance(v, (str, int, float, bool)) for v in resp.values()):
        return json.dumps(resp, indent=1, ensure_ascii=False)
    out = []
    for k, v in resp.items():
        t = "" if v is None else ("true" if v is True else "false" if v is False else str(v))
        out.append(f"{k}:\n{t}" if "\n" in t else f"{k}: {t}")
    return "\n".join(out)


def py_json(x):
    return json.dumps(x, ensure_ascii=False)


def render_value(v):
    if isinstance(v, str): return v
    if v is True: return "true"
    if v is False: return "false"
    if v is None: return "null"
    return py_json(v)


def call_text(calls):
    return "\n\n".join("<tool_call>\n<function=" + c["name"] + ">\n" + "".join(
        f"<parameter={k}>\n{render_value(v)}\n</parameter>\n" for k, v in c["arguments"].items()) + "</function>\n</tool_call>"
        for c in calls)


def lfm3_prompt(messages, tools, thinking=True):
    """toolformats/lfm3.js lfm3Prompt (plus the <|startoftext|> bos the shim adds)."""
    system, msgs = "", messages
    if msgs and msgs[0]["role"] == "system":
        system, msgs = msgs[0]["content"], msgs[1:]
    if tools:
        system += ("\n\n" if system else "") + "<tools>\n" + "\n".join(py_json(t) for t in tools) + "\n</tools>"
    out = "<|startoftext|>" + ("<|im_start|>system\n" + system + "<|im_end|>\n" if system else "")
    last = max([i for i, m in enumerate(msgs) if m["role"] == "assistant"], default=-1)
    for i, m in enumerate(msgs):
        if m["role"] == "assistant":
            out += "<|im_start|>assistant\n<think>" + (m.get("reasoning", "") if i == last else "") + "</think>" + m.get("content", "")
            if m.get("tool_calls"): out += call_text(m["tool_calls"])
            out += "<|im_end|>\n"
        elif m["role"] == "tool":
            c = m["content"]
            out += "<|im_start|>tool\n" + (c if "<tool_response>" in c else "<tool_response>\n" + c + "\n</tool_response>") + "<|im_end|>\n"
        else:
            out += "<|im_start|>" + m["role"] + "\n" + m["content"] + "<|im_end|>\n"
    return out + "<|im_start|>assistant\n" + ("<think>" if thinking else "<think></think>")


CALL_RE = re.compile(r"<tool_call>\s*<function=([\w.-]+)>(.*?)</function>\s*(?:</tool_call>|$)", re.S)
PARAM_RE = re.compile(r"<parameter=([\w.-]+)>\n?(.*?)\n?</parameter>", re.S)


def parse_output(raw):
    """Generation after '<think>': reasoning, visible text, tool calls."""
    if "</think>" in raw:
        reasoning, rest = raw.split("</think>", 1)
    else:
        reasoning, rest = raw, ""          # ran out while thinking
    calls = []
    for name, body in CALL_RE.findall(rest):
        args = {}
        for k, v in PARAM_RE.findall(body):
            v2 = v
            if v.strip()[:1] in "[{":
                try: v2 = json.loads(v)
                except Exception: pass
            args[k] = v2
        calls.append({"name": name, "arguments": args})
    text = rest.split("<tool_call>", 1)[0].strip()
    return reasoning.strip(), text, calls


# ── Tools ─────────────────────────────────────────────────────────────────────
class Shell:
    def __init__(self):
        import threading
        self.p = subprocess.Popen(["node", "shell.mjs"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.n = 0
        self.lock = threading.Lock()   # one shell process, many chat threads

    def run(self, chat, cmd):
        with self.lock:
            self.n += 1
            self.p.stdin.write(json.dumps({"id": self.n, "chat": str(chat), "cmd": cmd}) + "\n"); self.p.stdin.flush()
            return json.loads(self.p.stdout.readline())


TOK = re.compile(r"[a-z0-9][a-z0-9'-]*")
STOP = set("a an the and or but so to of in on at for is it its me my we our you your he she they that this what with like ok lol just be was are do does did can if not no yeah".split())


def bm25(docs, query, k=3):
    T = [[w for w in TOK.findall(d.lower()) if w not in STOP] for d in docs]
    q = [w for w in TOK.findall(query.lower()) if w not in STOP]
    if not T or not q: return []
    N, avg = len(T), sum(map(len, T)) / max(1, len(T))
    df = Counter(w for d in T for w in set(d))
    scores = []
    for i, d in enumerate(T):
        tf, s = Counter(d), 0.0
        for w in q:
            if tf[w]:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        scores.append((s, i))
    return [i for s, i in sorted(scores, reverse=True)[:k] if s > 0]


class Chat:
    """One replayed chat in one arm. step() is a generator: it yields prompts and receives raw generations."""

    def __init__(self, data, arm, shell, tok, log, max_turns=None):
        self.d, self.arm, self.shell, self.tok, self.log = data, arm, shell, tok, log
        self.chat_id = f"{arm}-{data['id']}"
        self.msgs = data["messages"]
        self.max_turns = max_turns
        self.remembered = []
        self.out_n = 0
        self.record = {"chat": data["id"], "arm": arm, "updates": [], "answer": None, "notes_history": []}

    # bash as tools/bash.js returns it to the model
    def bash(self, cmd, room_chars=6000):
        cmd = str(cmd or "").strip()
        if not cmd:
            return {"error": "The command was empty. Put the whole shell line in command, e.g. gh repo list, ls /repos or man."}
        r = self.shell.run(self.chat_id, cmd)
        out, err = r["stdout"], r["stderr"]
        model = {"exit_code": r["exitCode"]}
        limit = int(max(1500, room_chars - 400) * 0.85)
        if len(out) > limit:
            self.out_n += 1
            f = f"/tmp/out-{self.out_n}.txt"
            self.shell.run(self.chat_id, f"cat > {f} <<'SQUIGGLE_EOF'\n{out}\nSQUIGGLE_EOF")
            lines = len(out.rstrip("\n").split("\n"))
            model["stdout"] = wrap_untrusted("bash output", out[: int(limit * 0.6)] + f"\n… ({lines} lines, {len(out)} characters in all, too much for your window; the whole output is in {f}: grep it, or read it in pieces with sed -n or tail)")
            model["saved_to"] = f
        elif out:
            model["stdout"] = wrap_untrusted("bash output", out)
        if err:
            cut = int(max(1500, room_chars - 400) * 0.15)
            model["stderr"] = err if len(err) <= cut else err[:cut] + f"\n… ({len(err) - cut} more characters)"
        if not out and not err:
            model["stdout"] = "(no output)"
        return model

    def notes(self):
        r = self.shell.run(self.chat_id, f"cat {NOTES}")
        return r["stdout"] if r["exitCode"] == 0 else None

    def run_tool(self, call, upto):
        name, a = call["name"], call["arguments"]
        if name == "bash":
            return self.bash(a.get("command", ""))
        if name == "remember":
            fact = f"{a.get('subject', '')} → {a.get('relation', '')} → {a.get('object', '')}" + (f" ({a['note']})" if a.get("note") else "")
            self.remembered.append(fact)
            return {"ok": True, "id": f"f{len(self.remembered)}"}
        if name == "find":
            # Squiggle's find over "past chats": here, the earlier turns of this chat that are out of view, plus memory.
            earlier = [f"{m['role']}: {m['content']}" for m in self.msgs[:upto]]
            hits = [{"source": "earlier in this chat", "text": earlier[i][:500]} for i in bm25(earlier, str(a.get("query", "")))]
            hits += [{"source": "memory", "text": f} for f in self.remembered if any(w in f.lower() for w in TOK.findall(str(a.get("query", "")).lower()) if w not in STOP)][:3]
            return {"results": hits} if hits else {"results": [], "note": "Nothing found."}
        if name == "need":
            return {"answer": "The user isn't available to answer right now. Go with what you have and say what you assumed."}
        if name == "plan":
            return {"ok": True, "note": "Plans aren't run in this test: work it out in this reply."}
        if name == "tool_info":
            want = a.get("names") or []
            want = want if isinstance(want, list) else [want]
            return [t for t in TOOLS if t["name"] in want] or {"error": "No such tools; the ready ones are " + ", ".join(t["name"] for t in TOOLS)}
        if name == "done":
            return {"ok": True}
        return {"error": f"No tool named {name}. Tools ready to call: {', '.join(t['name'] for t in TOOLS)}."}

    def ntok(self, text):
        return len(self.tok.encode(text, add_special_tokens=False))

    def fit(self, head, window, tail):
        """[system] + window + tail, dropping the oldest window messages until the reply has MIN_REPLY room."""
        if self.arm == "full":
            msgs = [head] + window + tail
            p = lfm3_prompt(msgs, TOOLS)
            return p, MAX_OUTPUT, len(window)
        w = list(window)
        while True:
            p = lfm3_prompt([head] + w + tail, TOOLS)
            room = WINDOW - self.ntok(p)
            if room >= MIN_REPLY or not w:
                return p, max(64, min(MAX_OUTPUT, room)), len(w)
            w = w[1:]
            while w and w[0]["role"] != "user":
                w = w[1:]

    def loop(self, head, window, tail, rounds, upto, tag):
        """Generate, run tool calls, repeat. Returns the trace."""
        trace, tail = [], list(tail)
        for r in range(rounds + 1):
            prompt, max_new, kept = self.fit(head, window, tail)
            raw = yield (prompt, max_new)
            reasoning, text, calls = parse_output(raw)
            step = {"round": r, "prompt_tokens": self.ntok(prompt), "max_new": max_new, "window_msgs": kept,
                    "reasoning": reasoning, "text": text, "calls": calls, "finished_thinking": "</think>" in raw}
            trace.append(step)
            if not calls or r == rounds:
                if calls: step["note"] = "out of tool rounds"
                break
            results = []
            for c in calls:
                res = self.run_tool(c, upto)
                results.append(res)
            step["results"] = results
            tail.append({"role": "assistant", "content": text, "reasoning": reasoning, "tool_calls": calls})
            for c, res in zip(calls, results):
                tail.append({"role": "tool", "content": result_text(res)})
        return trace

    def pretend_cat(self):
        """The notes as a tool result the model already got (Squiggle prefetch style)."""
        call = {"name": "bash", "arguments": {"command": f"cat {NOTES}"}}
        return [{"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "content": result_text(self.bash(call["arguments"]["command"]))}]

    def window_before(self, i):
        """The last KEEP_EXCHANGES user turns (and their replies) before message i."""
        starts = [j for j in range(i) if self.msgs[j]["role"] == "user"]
        s = starts[-KEEP_EXCHANGES] if len(starts) >= KEEP_EXCHANGES else 0
        return [{"role": m["role"], "content": m["content"]} for m in self.msgs[s:i]]

    def step(self):
        head = {"role": "system", "content": SYSTEM}
        if self.arm == "notes":
            users = [i for i, m in enumerate(self.msgs) if m["role"] == "user"]
            if self.max_turns: users = users[: self.max_turns]
            for n, i in enumerate(users):
                reply = self.msgs[i + 1] if i + 1 < len(self.msgs) and self.msgs[i + 1]["role"] == "assistant" else None
                before = self.notes()
                tail = [{"role": "user", "content": self.msgs[i]["content"]}] + self.pretend_cat()
                if reply: tail.append({"role": "assistant", "content": reply["content"]})
                tail.append({"role": "user", "content": NUDGE})
                trace = yield from self.loop(head, self.window_before(i), tail, UPDATE_ROUNDS, i, "update")
                after = self.notes()
                self.record["updates"].append({"turn": n, "msg_index": i, "changed": before != after, "trace": trace})
                self.record["notes_history"].append(after)
            end = len(self.msgs) if not self.max_turns else (users[-1] + 2 if users else 0)
            tail = [{"role": "user", "content": self.d["question"]}] + self.pretend_cat()
            self.record["answer"] = yield from self.loop(head, self.window_before(end), tail, ANSWER_ROUNDS, end, "answer")
            self.record["final_notes"] = self.notes()
            self.record["remembered"] = self.remembered
        else:
            end = len(self.msgs)
            window = [{"role": m["role"], "content": m["content"]} for m in self.msgs] if self.arm == "full" else self.window_before(end)
            tail = [{"role": "user", "content": self.d["question"]}]
            self.record["answer"] = yield from self.loop(head, window, tail, ANSWER_ROUNDS, end, "answer")
            self.record["remembered"] = self.remembered


# ── Backends ──────────────────────────────────────────────────────────────────
class VLLM:
    def __init__(self):
        from vllm import LLM, SamplingParams
        self.SP = SamplingParams
        self.llm = LLM(MODEL, trust_remote_code=True, max_model_len=32768, gpu_memory_utilization=0.85, seed=0)
        self.tok = self.llm.get_tokenizer()

    def generate(self, items):
        from vllm.inputs import TokensPrompt
        prompts = [TokensPrompt(prompt_token_ids=self.tok.encode(p, add_special_tokens=False)) for p, _ in items]
        params = [self.SP(max_tokens=m, stop=["<|im_end|>"], seed=0, **SAMPLING) for _, m in items]
        outs = self.llm.generate(prompts, params, use_tqdm=False)
        return [o.outputs[0].text for o in outs]


class Llama:
    """llama.cpp's llama-server (built in the job) on Liquid's QAD Q4_0 GGUF: the file Squiggle's CPU build loads.
    Prompts go in as token ids (no extra BOS); outputs come back as token ids and are decoded with the HF tokenizer,
    so <think>, <tool_call> and the rest come through whatever the server's detokenizer does with them."""
    SLOTS, PER_SLOT = 24, 14336

    def __init__(self):
        import urllib.request
        from huggingface_hub import hf_hub_download
        from transformers import AutoTokenizer
        self.u = urllib.request
        self.tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
        gguf = hf_hub_download("LiquidAI/LFM3-1.7B-GGUF", "LFM3-1.7B-QAD-Q4_0.gguf")
        server = os.environ.get("LLAMA_SERVER", "llama.cpp/build/bin/llama-server")
        self.p = subprocess.Popen([server, "-m", gguf, "-ngl", "99", "-np", str(self.SLOTS), "-c", str(self.SLOTS * self.PER_SLOT),
                                   "--port", "8080", "--host", "127.0.0.1", "--no-webui", "--special"],
                                  stdout=open("llama-server.log", "w"), stderr=subprocess.STDOUT)
        for _ in range(600):
            try:
                if json.loads(self.u.urlopen("http://127.0.0.1:8080/health", timeout=2).read()).get("status") == "ok": break
            except Exception: pass
            if self.p.poll() is not None: raise RuntimeError("llama-server exited; see llama-server.log")
            time.sleep(1)

    def one(self, item):
        p, m = item
        body = {"prompt": self.tok.encode(p, add_special_tokens=False), "n_predict": m, "temperature": SAMPLING["temperature"],
                "top_k": SAMPLING["top_k"], "top_p": 1.0, "min_p": 0.0, "repeat_penalty": SAMPLING["repetition_penalty"],
                "stop": ["<|im_end|>"], "seed": 0, "cache_prompt": True, "return_tokens": True}
        req = self.u.Request("http://127.0.0.1:8080/completion", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(self.u.urlopen(req, timeout=900).read())
        if r.get("tokens"):
            return self.tok.decode(r["tokens"], skip_special_tokens=False).split("<|im_end|>")[0]
        return r.get("content", "")

    def generate(self, items):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(self.SLOTS) as ex:
            return list(ex.map(self.one, items))


class HF:
    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = AutoModelForCausalLM.from_pretrained(MODEL, trust_remote_code=True, dtype=torch.bfloat16).to(dev).eval()
        self.dev = dev

    def generate(self, items):
        outs = []
        for p, m in items:
            ids = self.tok(p, return_tensors="pt", add_special_tokens=False).input_ids.to(self.dev)
            with self.torch.no_grad():
                g = self.model.generate(ids, max_new_tokens=m, do_sample=True, temperature=SAMPLING["temperature"], top_k=SAMPLING["top_k"],
                                        top_p=1.0, repetition_penalty=SAMPLING["repetition_penalty"],
                                        eos_token_id=self.tok.convert_tokens_to_ids("<|im_end|>"))
            outs.append(self.tok.decode(g[0][ids.shape[1]:], skip_special_tokens=False).replace("<|im_end|>", ""))
        return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--chats", default="")
    ap.add_argument("--arms", default="notes,window,full")
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--backend", default="llama")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    data = json.load(open("data.json"))
    if a.chats: data = [d for d in data if str(d["id"]) in a.chats.split(",")]
    t0 = time.time()
    be = {"vllm": VLLM, "hf": HF, "llama": Llama}[a.backend]()
    print(f"model ready in {time.time() - t0:.0f}s; system prompt {len(be.tok.encode(lfm3_prompt([{'role': 'system', 'content': SYSTEM}], TOOLS), add_special_tokens=False))} tokens", flush=True)
    shell = Shell()
    log = open(os.path.join(a.out, "log.txt"), "a")
    chats = [Chat(d, arm, shell, be.tok, log, a.max_turns) for arm in a.arms.split(",") for d in data]
    if hasattr(be, "one"):
        # llama-server: every chat runs on its own, so no chat waits for the slowest one in a round.
        import threading
        from concurrent.futures import ThreadPoolExecutor
        lock, first = threading.Lock(), [True]

        def drive(c):
            g = c.step()
            try:
                item = next(g)
                while True:
                    out = be.one(item)
                    with lock:
                        if first[0]:
                            print("first raw output:", repr(out[:600]), flush=True); first[0] = False
                    item = g.send(out)
            except StopIteration:
                pass
            json.dump(c.record, open(os.path.join(a.out, f"{c.arm}-{c.d['id']}.json"), "w"), indent=1, ensure_ascii=False)
            print(f"done {c.arm}-{c.d['id']} at {(time.time() - t0) / 60:.1f} min", flush=True)

        def progress():
            while True:
                time.sleep(120)
                n = sum(len(c.record["updates"]) for c in chats)
                print(f"progress: {n} turns noted, {(time.time() - t0) / 60:.1f} min", flush=True)
                for c in chats:   # partial records, so a run cut off by its time limit still leaves its notes
                    if c.arm == "notes" and c.record["updates"]:
                        json.dump(c.record, open(os.path.join(a.out, f"partial-{c.arm}-{c.d['id']}.json"), "w"), ensure_ascii=False)
        threading.Thread(target=progress, daemon=True).start()
        with ThreadPoolExecutor(len(chats)) as ex:
            list(ex.map(drive, chats))
        print(f"all done in {(time.time() - t0) / 60:.1f} min", flush=True)
        return
    gens = [c.step() for c in chats]
    pending = {}
    for i, g in enumerate(gens):
        try: pending[i] = next(g)
        except StopIteration: pass
    rounds = ntoks = 0
    while pending:
        keys = list(pending)
        outs = be.generate([pending[k] for k in keys])
        if rounds == 0: print('first raw output:', repr(outs[0][:600]), flush=True)
        rounds += 1
        ntoks += sum(len(o) for o in outs) // 4
        for k, o in zip(keys, outs):
            try: pending[k] = gens[k].send(o)
            except StopIteration:
                del pending[k]
                c = chats[k]
                json.dump(c.record, open(os.path.join(a.out, f"{c.arm}-{c.d['id']}.json"), "w"), indent=1, ensure_ascii=False)
                print(f"done {c.arm}-{c.d['id']} at {(time.time() - t0) / 60:.1f} min", flush=True)
        if rounds % 10 == 0:
            print(f"batch {rounds}: {len(pending)} chats going, ~{ntoks} tokens out, {(time.time() - t0) / 60:.1f} min", flush=True)
    print(f"all done in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
