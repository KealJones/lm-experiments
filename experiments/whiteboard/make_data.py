"""Bundles the 16 context-packets chats (../context-packets/data) into data.json: messages + final question."""
import json, re
D = "../context-packets/data"

def turns(text):
    out, cur = [], []
    for para in text.split("\n\n"):
        if re.match(r"^(User|Assistant):", para) and cur:
            out.append("\n\n".join(cur)); cur = []
        cur.append(para)
    if cur: out.append("\n\n".join(cur))
    return out

data = []
for t in range(1, 17):
    msgs = []
    for x in turns(open(f"{D}/convs/conv{t}.md").read()):
        role, body = x.split(":", 1)
        msgs.append({"role": role.strip().lower(), "content": body.strip()})
    data.append({"id": t, "messages": msgs, "question": open(f"{D}/questions/q{t}.txt").read().strip()})
    print(t, sum(m["role"] == "user" for m in msgs), "user turns", sum(len(m["content"].split()) for m in msgs), "words")
json.dump(data, open("data.json", "w"), indent=0)
