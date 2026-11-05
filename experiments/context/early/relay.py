"""Context-relay test: Qwen3 0.6B, 4,096-token window.
Round 1: ask for a TypeScript tic-tac-toe game.
If generation hits the context limit, take exactly the code it had written,
start a FRESH chat (no history, no explanation) with:
  "can you complete this games code\n\n<code>"
Repeat until the model ends on its own / says it's done (or MAX_ROUNDS).
"""
import json, re, sys, time
from llama_cpp import Llama

MODEL = sys.argv[1]
OUT = sys.argv[2]
N_CTX = 4096
MAX_ROUNDS = 10

llm = Llama(model_path=MODEL, n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)

def render(user):
    # Qwen3 chat template, thinking off (empty think block) so the window goes to code
    return (f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n\n</think>\n\n")

def extract_code(text):
    # everything from the first code fence onward (the code it had), fence line removed
    m = re.search(r"```[a-zA-Z]*\n", text)
    code = text[m.end():] if m else text
    # if it closed the fence, drop the closing fence and anything after
    code = code.split("```")[0]
    return code

log = []
prompt_user = "Write me a TypeScript tic tac toe game."
for rnd in range(1, MAX_ROUNDS + 1):
    p = render(prompt_user)
    ptoks = llm.tokenize(p.encode(), add_bos=False, special=True)
    room = N_CTX - len(ptoks)
    entry = {"round": rnd, "prompt_user": prompt_user, "prompt_tokens": len(ptoks), "room": room}
    if room <= 16:
        entry["result"] = "prompt alone fills the 4K window - cannot continue"
        log.append(entry); break
    t = time.time()
    r = llm.create_completion(p, max_tokens=room, temperature=0.7, top_p=0.8, top_k=20,
                              repeat_penalty=1.05, stop=["<|im_end|>"])
    out = r["choices"][0]["text"]
    fin = r["choices"][0]["finish_reason"]  # 'length' = ran out of context, 'stop' = ended itself
    entry.update(output=out, finish=fin, gen_tokens=r["usage"]["completion_tokens"],
                 secs=round(time.time() - t, 1))
    log.append(entry)
    print(f"round {rnd}: prompt {len(ptoks)} tok, gen {entry['gen_tokens']} tok, finish={fin}, {entry['secs']}s", flush=True)
    json.dump(log, open(OUT, "w"), indent=1)
    if fin != "length":
        entry["result"] = "model ended on its own"
        break
    prompt_user = "can you complete this games code\n\n" + extract_code(out)
json.dump(log, open(OUT, "w"), indent=1)
print("DONE", flush=True)
