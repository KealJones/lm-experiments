"""The ten resume strategies. Each takes a Ctx and leaves the final game in ctx.ws.game."""
import re
from core import *

WRITE_ME = "Write me " + TASK + "."
SKELETON_REQ = (GOAL + "\n\nWrite the skeleton of the whole game as one TypeScript code block: types, top-level "
    "variables with their types, and every function with its full typed signature and a one-line comment above it "
    "saying what it does. Every function body must be only `// TODO`. Include the code at the bottom that sets up "
    "the page and starts the game.")
MAX_CHATS = 8

def chat_text(rec): return "".join(s["output"] for s in rec.get("steps", []))

class Ctx:
    def __init__(self, ws, think, deadline):
        self.ws, self.think, self.deadline, self.log = ws, think, deadline, []
        self.notes = []
    def plain(self, user, tag, **kw): return plain_chat(user, self.think, self.log, tag, deadline=self.deadline, **kw)
    def tools(self, user, tools, tag): return tool_chat(user, tools, self.think, self.ws, self.log, tag, deadline=self.deadline)

# ---- helpers for skeleton-based strategies
def collapsed(ws, keep=None):
    """game.ts with every implemented (non-TODO) function body except `keep` collapsed to { ... }."""
    src, o = ws.read(), outline(ws.game)
    if not o: return src
    for f in sorted(o["functions"], key=lambda f: -f["start"]):
        if f["name"] != keep and not f.get("todo") and "bodyStart" in f:
            src = src[:f["bodyStart"]] + "{ /* implemented */ }" + src[f["bodyEnd"]:]
    return src

def make_skeleton(c, think=None):
    t = c.think
    if think: c.think = think
    out, fin = c.plain(SKELETON_REQ, "skeleton")
    c.think = t
    sk = all_code(out) if "```" in strip_think(out) else (latest_code(out) or "")
    c.ws.write(sk)
    enforce_skeleton(c)
    c.notes.append(f"bare skeleton scores {score(c.ws.game)['points']}/5")
    return c.ws.read()

def enforce_skeleton(c):
    """The model rarely leaves bodies empty, so make it a real skeleton in code:
    drop duplicate functions (keep the first), and empty every function body to // TODO."""
    o = outline(c.ws.game)
    if not o: return
    src, seen, edits = c.ws.read(), set(), []
    for f in sorted(o["functions"], key=lambda f: f["start"]):
        if f["name"] in seen: edits.append((f["start"], f["end"], ""))
        else:
            seen.add(f["name"])
            if "bodyStart" in f: edits.append((f["bodyStart"], f["bodyEnd"], "{\n  // TODO\n}"))
    vseen = set()
    for v in sorted(o["vars"], key=lambda v: v["start"]):
        if v["name"] in vseen or v["name"] in seen: edits.append((v["start"], v["end"], ""))
        vseen.add(v["name"])
    done_spans = set()
    for s, e, rep in sorted(edits, key=lambda x: -x[0]):
        if (s, e) in done_spans: continue
        done_spans.add((s, e)); src = src[:s] + rep + src[e:]
    c.ws.write(src)
    c.notes.append(f"skeleton: {len(seen)} functions emptied to TODO, {len(o['functions']) - len(seen)} duplicates dropped")

def todo_functions(ws):
    o = outline(ws.game)
    return [f for f in (o or {}).get("functions", []) if f.get("todo")]

def fn_from(code, name):
    return code if code and re.search(r"\b(function\s+" + re.escape(name) + r"\b|(const|let|var)\s+" + re.escape(name) + r"\b)", code) else None

def fill_one(c, f, extra="", tag="fill"):
    user = (GOAL + "\n\nHere is the skeleton of game.ts:\n```typescript\n" + collapsed(c.ws, keep=f["name"]) +
            "\n```\n\n" + extra + "Write the complete code for the function `" + f["sig"] +
            "`. Reply with only that whole function in one TypeScript code block.")
    out, fin = c.plain(user, tag)
    code = fn_from(latest_code(out), f["name"])
    if code: c.ws.replace_function(f["name"], code)
    return code, out

# ---- A. baseline relay (the original test)
def A(c):
    user, last = WRITE_ME, None
    for i in range(MAX_CHATS):
        r = c.tools(user, ["run_typescript"], f"chat{i+1}")
        code = latest_code(chat_text(c.log[-1]))
        if code: last = code
        if r != "full": break
        if c.log[-1]["prompt_tokens"] > N_CTX - 200: c.notes.append("handed-back code alone filled the window"); break
        if last: user = "can you complete this games code\n\n" + last
    c.ws.write(last or "")

# ---- B. write to a file; resume = computed outline + file tail
def B(c):
    tools = ["append_file", "view_file", "run_typescript", "finish"]
    user = GOAL + "\n\nWrite the game into game.ts with append_file, in pieces of at most 60 lines. Check it with run_typescript. Call finish when it works."
    for i in range(MAX_CHATS):
        r = c.tools(user, tools, f"chat{i+1}")
        if not c.ws.read().strip():
            code = latest_code(chat_text(c.log[-1]))
            if code: c.ws.write(code); c.notes.append(f"chat{i+1}: wrote code in the reply, not the file (fallback used)")
        if r in ("finished", "ended") and c.ws.read().strip(): break
        user = (GOAL + "\n\nYou were writing game.ts and got cut off. Outline of game.ts so far:\n" + c.ws.outline_text() +
                "\n\nLast lines of game.ts:\n" + c.ws.tail() + "\n\nContinue the game from where it stopped: add the rest "
                "with append_file, check with run_typescript, call finish when it works.")

# ---- C. skeleton first, then one fresh chat per function
def C(c):
    make_skeleton(c)
    for f in todo_functions(c.ws): fill_one(c, f)

# ---- D. skeleton (Qwen3, thinking off) + fill-in-the-middle with Qwen2.5-Coder 0.5B
def D(c):
    make_skeleton(c, think="off")
    done = set()
    for _ in range(20):
        todo = [f for f in todo_functions(c.ws) if f["name"] not in done]
        if not todo or time.time() > c.deadline: break
        f = todo[0]; done.add(f["name"])
        src = c.ws.read()
        prefix, suffix = src[:f["bodyStart"] + 1] + "\n  ", "\n" + src[f["bodyEnd"] - 1:]
        while tok(prefix + suffix, CODER) > 3000 and len(prefix) > 200: prefix = prefix[len(prefix) // 5:]
        p = "<|fim_prefix|>" + prefix + "<|fim_suffix|>" + suffix + "<|fim_middle|>"
        t = time.time()
        r = model(CODER).create_completion(p, max_tokens=min(900, N_CTX - tok(p, CODER) - 8), temperature=0.2, top_p=0.9,
                                           stop=["<|endoftext|>", "<|fim_pad|>", "<|file_sep|>", "<|im_end|>", "<|fim_prefix|>"])
        mid = r["choices"][0]["text"]
        c.log.append({"tag": f"fim:{f['name']}", "prefix_tail": prefix[-300:], "suffix_head": suffix[:200], "output": mid,
                      "finish": r["choices"][0]["finish_reason"], "secs": round(time.time() - t, 1)})
        src = c.ws.read()
        c.ws.write(src[:f["bodyStart"] + 1] + "\n  " + mid.strip() + "\n" + src[f["bodyEnd"] - 1:])

# ---- E. notes file (state whiteboard); resume = NOTES.md + file tail
def E(c):
    tools = ["append_file", "write_notes", "run_typescript", "finish"]
    user = (GOAL + "\n\nWrite the game into game.ts with append_file, in pieces of at most 60 lines. Keep NOTES.md up to date "
            "with write_notes: what's done, what's next, and the key names and their types. Check with run_typescript. "
            "Call finish when it works.")
    for i in range(MAX_CHATS):
        r = c.tools(user, tools, f"chat{i+1}")
        if not c.ws.read().strip():
            code = latest_code(chat_text(c.log[-1]))
            if code: c.ws.write(code); c.notes.append(f"chat{i+1}: wrote code in the reply, not the file (fallback used)")
        if r in ("finished", "ended") and c.ws.read().strip(): break
        notes = open(c.ws.notes).read().strip() or "(empty)"
        user = (GOAL + "\n\nYou got cut off while writing game.ts. Your NOTES.md:\n" + notes + "\n\nLast lines of game.ts:\n" +
                c.ws.tail() + "\n\nContinue from where it stopped with append_file, keep NOTES.md updated, call finish when it works.")

# ---- F. context shift: same reply keeps going, oldest generated tokens dropped (system + request pinned)
def F(c):
    user = WRITE_ME + " Put the whole game in one TypeScript code block."
    base = render(FILLER, user)
    full, kept = "", None
    m = model()
    for i in range(MAX_CHATS):
        t = time.time()
        if kept is None:
            out, fin = segment(base, c.think, deadline=c.deadline)
        else:
            if time.time() > c.deadline: break
            p = base + kept
            r = m.create_completion(p, max_tokens=N_CTX - tok(p), stop=["<|im_end|>"], **(SAMPLE if c.think == "on" else SAMPLE_OFF))
            out, fin = r["choices"][0]["text"], r["choices"][0]["finish_reason"]
        full += out
        c.log.append({"tag": f"window{i+1}", "kept_tokens": tok(kept) if kept else 0, "output": out, "finish": fin, "secs": round(time.time() - t, 1)})
        if fin != "length": break
        ids = m.tokenize(full.encode(), add_bos=False, special=True)
        tail = m.detokenize(ids[-1400:]).decode("utf-8", "ignore")
        kept = tail[tail.find("\n") + 1:] if "\n" in tail else tail
    c.ws.write(all_code(full))

# ---- G. squeeze at 80%: summarize progress, continue with summary + tail
def G(c):
    limit = int(N_CTX * 0.8)
    out, fin = segment(render(FILLER, WRITE_ME + " Put the whole game in one TypeScript code block."), c.think, deadline=c.deadline, limit=limit)
    c.log.append({"tag": "write1", "output": out, "finish": fin})
    code = (all_code(out) if "```" in strip_think(out) else latest_code(out)) or ""
    summary = ""
    for i in range(MAX_CHATS - 1):
        if fin != "length": break
        piece = code if tok(code) < 2200 else code[-6000:]
        s_user = ("Code for this goal was being written and got cut off.\n" + GOAL + "\n\nCode so far" +
                  (" (end of it)" if piece is not code else "") + ":\n```typescript\n" + piece + "\n```\n" +
                  ("Earlier summary:\n" + summary + "\n" if summary else "") +
                  "Summarize the progress in at most 6 short lines: what's written, the key names and their types, and what's still left to write.")
        s_out, _ = c.plain(s_user, f"squeeze{i+1}")
        summary = strip_think(s_out)[:1200]
        tail = "\n".join(code.split("\n")[-25:])
        w_user = (GOAL + "\n\nProgress so far:\n" + summary + "\n\nThe code currently ends with:\n```typescript\n" + tail +
                  "\n```\nContinue writing the code from exactly where it stops. Output only the new code in one TypeScript code block.")
        out, fin = segment(render(FILLER, w_user), c.think, deadline=c.deadline, limit=limit)
        c.log.append({"tag": f"write{i+2}", "user": w_user, "output": out, "finish": fin})
        new = latest_code(out)
        if new: code = code.rstrip() + "\n" + new
    c.ws.write(code)

# ---- H. edits, not rewrites: code lives in game.ts; resume = "complete this game's code, it's in game.ts"
def H(c):
    tools = ["view_file", "edit_file", "append_file", "run_typescript", "finish"]
    user = (WRITE_ME + " Write it into game.ts with append_file (pieces of at most 60 lines), check it with run_typescript, "
            "and fix problems with edit_file instead of rewriting.")
    for i in range(MAX_CHATS):
        r = c.tools(user, tools, f"chat{i+1}")
        if not c.ws.read().strip():
            code = latest_code(chat_text(c.log[-1]))
            if code: c.ws.write(code); c.notes.append(f"chat{i+1}: wrote code in the reply, not the file (fallback used)")
        if r in ("finished", "ended") and c.ws.read().strip(): break
        n = c.ws.read().count("\n") + 1
        user = (f"can you complete this game's code? It's in game.ts ({n} lines). Use view_file to read it, and "
                "edit_file / append_file to change it. Check with run_typescript and call finish when it works.")

# ---- I. tests as the brief: per function, write a test, then the code to pass it (one retry with the error)
def I(c):
    make_skeleton(c)
    for f in todo_functions(c.ws):
        if time.time() > c.deadline: break
        user = (GOAL + "\n\nHere is the skeleton of game.ts:\n```typescript\n" + collapsed(c.ws) + "\n```\n\nWrite one small "
                "test for `" + f["sig"] + "` using console.assert, as a TypeScript code block. Only the test, no implementation.")
        out, _ = c.plain(user, f"test:{f['name']}")
        test = latest_code(out) or ""
        extra = "It must pass this test:\n```typescript\n" + test + "\n```\n\n" if test else ""
        code, _ = fill_one(c, f, extra, tag=f"impl:{f['name']}")
        if not test: continue
        p = f"{c.ws.d}/test_{f['name']}.ts"; open(p, "w").write(c.ws.read() + "\n\n" + test)
        rep = sandbox(p)
        c.log.append({"tag": f"check:{f['name']}", "report": rep[:800]})
        if re.search(r"TypeScript errors|Runtime error|assert failed", rep):
            fill_one(c, f, extra + "Your last attempt failed with:\n" + rep[:600] + "\n\n", tag=f"retry:{f['name']}")

# ---- J. combined: skeleton in game.ts + replace_function + computed outline + NOTES.md + tail on resume
def J(c):
    make_skeleton(c)
    tools = ["replace_function", "view_file", "run_typescript", "write_notes", "finish"]
    for i in range(MAX_CHATS):
        if not todo_functions(c.ws) and i > 0: break
        notes = open(c.ws.notes).read().strip() or "(empty)"
        user = (GOAL + "\n\nOutline of game.ts (computed from the file):\n" + c.ws.outline_text() + "\n\nNOTES.md:\n" + notes +
                ("\n\nLast lines of game.ts:\n" + c.ws.tail(15) if i > 0 else "") +
                "\n\nFill in the [TODO] functions one at a time with replace_function. After each one, check with "
                "run_typescript. Keep NOTES.md updated with write_notes. Call finish when the game works.")
        r = c.tools(user, tools, f"chat{i+1}")
        if r == "finished": break

STRATEGIES = {"A": A, "B": B, "C": C, "D": D, "E": E, "F": F, "G": G, "H": H, "I": I, "J": J}
