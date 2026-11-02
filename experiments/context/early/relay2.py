"""Context-relay test v2: Qwen3 0.6B, 4,096-token window, thinking ON,
a run_typescript sandbox tool, 3 junk tools and a padded system prompt.

Each "chat" = system + user message, then the model may call tools repeatedly.
If the window fills (mid-generation, or a tool result won't fit), take the latest
code it had (from a ``` block or a run_typescript call, partial is fine), and start
a FRESH chat (same system prompt, no history) whose only user message is:
  "can you complete this games code\n\n<code>"
Stop when the model ends a reply on its own (no tool call).
"""
import json, re, subprocess, sys, time, os
from llama_cpp import Llama

MODEL, OUT, SBX = sys.argv[1], sys.argv[2], sys.argv[3]
WORK = os.path.dirname(OUT)
N_CTX, MAX_CHATS, DEADLINE = 4096, 15, time.time() + 75 * 60

llm = Llama(model_path=MODEL, n_ctx=N_CTX, n_threads=2, seed=42, verbose=False)

FILLER = """You are Pip, the friendly assistant for Brightleaf Software Co. Brightleaf was founded in 2011 and makes tools for small teams. Our values are Clarity, Kindness, Craft, Curiosity and Ownership. Always be warm but professional.

Style guide:
- Use American English spelling. Prefer "color" over "colour".
- Never use more than one exclamation mark per reply.
- Refer to customers as "folks" or "teams", never "users" in marketing copy.
- Dates are written as "March 3, 2026", never "3/3/26".
- Product names are always capitalized: Brightleaf Notes, Brightleaf Boards, Brightleaf Sync, Brightleaf Pulse.
- Do not mention competitors by name. If asked, say you can only speak to Brightleaf products.
- Emoji are allowed in casual chats only, at most two per message.

Office information: The Portland office is open 8am to 6pm Pacific, Monday to Friday. The Austin office is open 9am to 5pm Central. The cafeteria serves vegetarian options on Tuesdays and Thursdays. Parking validation is available at the front desk. The wifi network for guests is "Brightleaf-Guest".

Support policy: Refunds are available within 30 days of purchase for annual plans. Monthly plans can be cancelled any time but are not refunded for partial months. Enterprise customers have a dedicated success manager. Escalations go to the support lead on call. Security issues should be reported to the security team and never discussed in public channels.

Pricing (for reference only, do not quote unless asked): Starter is $8 per seat per month, Team is $14 per seat per month, Business is $22 per seat per month, Enterprise is custom. Nonprofits receive a 40% discount. Students receive Starter free with a school email.

Holiday schedule: offices are closed on New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving and the day after, and December 24 through January 1.

Brand voice examples:
Good: "Happy to help with that. Here's what I found."
Bad: "OMG yes!!! Totally on it!!!"
Good: "That isn't supported yet, but here's a workaround."
Bad: "Nope, can't do that."

Remember that every conversation is logged for quality purposes. Be concise unless the person asks for detail. If you write code, write complete, working code. When the code is complete and working, say DONE."""

TOOLS = [
  {"type": "function", "function": {"name": "run_typescript", "description": "Type-check and run TypeScript code in a sandbox (fake browser DOM; prompt() returns null). Returns type errors, runtime errors and console output.", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "The full TypeScript source to check and run."}}, "required": ["code"]}}},
  {"type": "function", "function": {"name": "get_weather", "description": "Get the current weather for a city.", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
  {"type": "function", "function": {"name": "search_company_wiki", "description": "Search the Brightleaf internal wiki.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
  {"type": "function", "function": {"name": "send_slack_message", "description": "Send a message to a Brightleaf Slack channel.", "parameters": {"type": "object", "properties": {"channel": {"type": "string"}, "text": {"type": "string"}}, "required": ["channel", "text"]}}},
]

SYSTEM = (FILLER + "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
          "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
          + "\n".join(json.dumps(t) for t in TOOLS) +
          "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
          "<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>")

def tok(s): return len(llm.tokenize(s.encode(), add_bos=False, special=True))

def run_tool(name, args, n):
    if name == "run_typescript":
        path = os.path.join(WORK, f"sbx_{n}.ts")
        open(path, "w").write(str(args.get("code", "")))
        try:
            r = subprocess.run(["node", SBX, path], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
            return (r.stdout or r.stderr or "(no output)").strip()[:1200]
        except subprocess.TimeoutExpired:
            return "Sandbox timeout: the code ran for more than 15 seconds (infinite loop?)."
    return "This tool is unavailable in this environment."

def strip_think(s): return re.sub(r"<think>.*?(</think>|$)", "", s, flags=re.S)

def unescape_partial(s):
    s = re.sub(r"\\$", "", s)
    try: return json.loads('"' + s + '"')
    except Exception: return s.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t").replace("\\\\", "\\")

def latest_code(text):
    """Latest code in the assistant's (non-thinking) text: a ``` block or a run_typescript code arg, partial ok."""
    t = strip_think(text)
    cands = []
    for m in re.finditer(r"```[a-zA-Z]*\n(.*?)(```|$)", t, re.S):
        cands.append((m.start(), m.group(1)))
    for m in re.finditer(r'"code"\s*:\s*"((?:[^"\\]|\\.)*)("|$)', t, re.S):
        cands.append((m.start(), unescape_partial(m.group(1))))
    cands = [c for c in cands if c[1].strip()]
    return max(cands)[1] if cands else None

log, last_code, user_msg, ncall = [], None, "Write me a TypeScript tic tac toe game.", 0
for chat in range(1, MAX_CHATS + 1):
    prompt = f"<|im_start|>system\n{SYSTEM}<|im_end|>\n<|im_start|>user\n{user_msg}<|im_end|>\n<|im_start|>assistant\n"
    entry = {"chat": chat, "user": user_msg, "system_tokens": tok(SYSTEM), "steps": []}
    log.append(entry)
    assistant_text, ended = "", None
    while True:
        room = N_CTX - tok(prompt)
        if room < 32:
            ended = "window full before the model could reply (tool result filled it)"; break
        t = time.time()
        r = llm.create_completion(prompt, max_tokens=room, temperature=0.6, top_p=0.95, top_k=20,
                                  presence_penalty=0.5, stop=["<|im_end|>", "</tool_call>"])
        out, fin = r["choices"][0]["text"], r["choices"][0]["finish_reason"]
        step = {"prompt_tokens": tok(prompt), "gen_tokens": r["usage"]["completion_tokens"], "finish": fin, "secs": round(time.time() - t, 1), "output": out}
        entry["steps"].append(step)
        assistant_text += out
        print(f"chat {chat} step {len(entry['steps'])}: prompt {step['prompt_tokens']} + gen {step['gen_tokens']} tok, {fin}, {step['secs']}s", flush=True)
        json.dump(log, open(OUT, "w"), indent=1)
        if fin == "length":
            ended = "ran out of context mid-answer"; break
        m = re.search(r"<tool_call>\s*(\{.*\})\s*$", out, re.S)
        if "<tool_call>" in out and m:
            try:
                call = json.loads(m.group(1)); name, args = call.get("name"), call.get("arguments", {}) or {}
            except Exception as e:
                name, args = None, {}
                res = f"Could not parse tool call JSON: {e}"
            if name: ncall += 1; res = run_tool(name, args, ncall)
            step["tool"] = name; step["tool_result"] = res
            print(f"   tool {name}: {res[:160]!r}", flush=True)
            prompt += out + "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n" + res + "\n</tool_response><|im_end|>\n<|im_start|>assistant\n"
            assistant_text += "</tool_call>"
            continue
        ended = "model finished on its own"; break
    entry["ended"] = ended
    c = latest_code(assistant_text)
    if c: last_code = c
    entry["said_done"] = bool(re.search(r"\bdone\b", strip_think(assistant_text), re.I))
    json.dump(log, open(OUT, "w"), indent=1)
    print(f"chat {chat} ended: {ended}; said done: {entry['said_done']}", flush=True)
    if ended == "model finished on its own" or time.time() > DEADLINE:
        break
    if not last_code:
        entry["note"] = "no code written yet; re-sending original request"
        continue
    user_msg = "can you complete this games code\n\n" + last_code
open(os.path.join(WORK, "final.ts"), "w").write(last_code or "")
json.dump(log, open(OUT, "w"), indent=1)
print("DONE", flush=True)
