"""The same from-scratch-with-tools test as agent.py, for Gemma 4 models served by llama.cpp (llama-server), in
Gemma 4's native tool format (<|tool_call>call:name{arg:<|"|>...<|"|>}<tool_call|>, answered in the same model turn
with <|tool_response>response:name{value:<|"|>...<|"|>}<tool_response|>), as in findout2/gemma_eval.py.

Same task prompt, system prompt, tools, docs, turn limit, attempts and lenient grading as agent.py.

  python gemma_agent.py worker --model gemma4-e2b --server http://127.0.0.1:8080 --tag pilot|full
  python agent.py report        (covers these files too)
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import re
import threading
import time
import urllib.request

import agent
import run as base

MODELS = {  # name -> (GGUF repo, file, what it is)
    "gemma4-e2b": ("unsloth/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q8_0.gguf", "Gemma 4 E2B-it, Q8_0"),
    "tiny-gemma4": ("kealjones/tiny-gemma4-test", "tiny-gemma4-heal3-v2-Q4_0.gguf",
                    "Keal's tiny Gemma 4 (heal 3, 0.6B body), Q4_0 phone build"),
}
TEMPLATE_FROM = "google/gemma-4-E2B-it"  # chat template + tool rendering (the tiny model was healed on this format)
CALL = re.compile(r"<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>", re.S)
ARG = re.compile(r'(\w+):(?:<\|"\|>(.*?)<\|"\|>|([^,}]*))', re.S)
STOPS = ["<turn|>", "<|tool_response>", "<eos>"]


def parse(text):
    """Gemma 4 output -> (visible text, [(name, args)], body up to and including the last call)."""
    t = re.sub(r"<\|channel>.*?<channel\|>", "", text, flags=re.S)
    calls = [(m.group(1), {k: (s if s is not None else v.strip()) for k, s, v in ARG.findall(m.group(2))})
             for m in CALL.finditer(t)]
    vis = CALL.sub("", t)
    for s in STOPS + ["<pad>"]:
        vis = vis.replace(s, "")
    body = text[:text.rfind("<tool_call|>") + len("<tool_call|>")] if calls else text
    return vis.strip(), calls, body


def complete(server, prompt, max_tokens, seed):
    req = urllib.request.Request(server + "/completion", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"prompt": prompt, "n_predict": max_tokens, "temperature": 1.0,
                                                  "top_p": 0.95, "top_k": 64, "seed": seed, "stop": STOPS,
                                                  "cache_prompt": True, "return_tokens": True}).encode())
    with urllib.request.urlopen(req, timeout=1800) as r:
        j = json.loads(r.read())
    return j


def detok(server, tokens):
    req = urllib.request.Request(server + "/detokenize", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"tokens": tokens}).encode())
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["content"]


def count_tokens(server, text):
    req = urllib.request.Request(server + "/tokenize", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"content": text, "add_special": False, "parse_special": True}).encode())
    with urllib.request.urlopen(req, timeout=300) as r:
        return len(json.loads(r.read())["tokens"])


def converse(c, server, tok, max_turns, seed):
    lang = c["lang"]
    msgs = [{"role": "system", "content": agent.system(lang)}, {"role": "user", "content": c["user"]}]
    prompt = tok.apply_chat_template(msgs, tools=agent.TOOLS, tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False)
    prompt = prompt.removeprefix("<bos>")  # llama-server adds BOS itself
    c["prompt0"] = prompt
    c["raw"] = []
    while True:
        if count_tokens(server, prompt) > agent.MAX_CONTEXT:
            c["end"] = "context full"
            return
        j = complete(server, prompt, 900, seed + c["turns"])
        # content may hide special tokens, so rebuild the text from the token ids
        text = detok(server, j["tokens"]) if j.get("tokens") else j.get("content", "")
        stop = j.get("stopping_word") or ""
        c["turns"] += 1
        c["raw"].append(text + stop)
        vis, calls, body = parse(text)
        if not calls:
            c["msgs"].append({"role": "assistant", "content": vis})
            blocks = re.findall(r"```[^\n`]*\n(.*?)```", vis, re.S)
            c["final_code"] = blocks[-1] if blocks else None
            c["end"] = "answered"
            return
        c["msgs"].append({"role": "assistant", "content": vis, "tool_calls": [{"name": n, "arguments": a} for n, a in calls]})
        results = []
        for n, a in calls:
            c["tools"][n] = c["tools"].get(n, 0) + 1
            if n == "run":
                c["last_run_code"] = a.get("code")
            r = agent.call_tool(lang, n, a)
            results.append(r)
            c["msgs"].append({"role": "tool", "name": n, "content": r})
        prompt += body + "".join(f'<|tool_response>response:{n}{{value:<|"|>{r}<|"|>}}<tool_response|>'
                                 for (n, _), r in zip(calls, results))
        if c["turns"] >= max_turns:
            c["end"] = "turn limit"
            return


def worker(model, server, tag, threads):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TEMPLATE_FROM)
    t0 = time.time()
    tasks = [t for t in base.TASKS if t[0] in base.PILOT_TASKS[:2]] if tag == "pilot" else base.TASKS
    attempts = 1 if tag == "pilot" else agent.ATTEMPTS
    max_turns = 6 if tag == "pilot" else agent.MAX_TURNS
    convs = [dict(model=model, lang=lang, task=tid, attempt=a, expected=exp, end="", turns=0,
                  tools={k: 0 for k in agent.TOOL_FNS}, last_run_code=None, final_code=None,
                  user=agent.task_prompt(lang, desc), msgs=[])
             for lang in ["zig", "plink"] for a in range(attempts) for tid, desc, exp in tasks]
    done, lock = [0], threading.Lock()

    def one(k):
        c = convs[k]
        try:
            converse(c, server, tok, max_turns, seed=1000 * k)
        except Exception as e:  # keep going; record it
            c["end"] = f"error: {type(e).__name__}: {e}"[:300]
        code = c["final_code"] or c["last_run_code"]
        c["graded_code"] = "final answer" if c["final_code"] else ("last run" if code else "none")
        c["verdict"], c["detail"] = agent.lenient(c["lang"], code, c["expected"]) if code else ("wrong", "no code")
        with lock:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(convs):
                print(f"  {model}: {done[0]}/{len(convs)} done, {sum(x.get('verdict') == 'pass' for x in convs)} pass "
                      f"({time.time() - t0:.0f}s)", flush=True)

    with cf.ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, range(len(convs))))
    for lang in ["zig", "plink"]:
        cs = [c for c in convs if c["lang"] == lang]
        out = {"model": MODELS[model][2], "lang": lang, "tag": tag, "seconds": round(time.time() - t0), "convs": cs}
        pathlib.Path(f"agent_{tag}_{model}_{lang}.json").write_text(json.dumps(out, indent=1))
        solved = {c["task"] for c in cs if c["verdict"] == "pass"}
        print(f"== {model} {lang} {tag}: pass {sum(c['verdict'] == 'pass' for c in cs)}/{len(cs)}, tasks solved "
              f"{len(solved)}/{len(tasks)}, doc lookups {sum(c['tools']['grep'] + c['tools']['read'] for c in cs)}, "
              f"errors {sum(c['end'].startswith('error') for c in cs)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["worker"])
    ap.add_argument("--model", choices=list(MODELS))
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--tag", default="full")
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    worker(a.model, a.server, a.tag, a.threads)
