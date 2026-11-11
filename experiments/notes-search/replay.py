"""Replay a 4a chat's note passes from the saved outputs: what read_notes showed at the turns matching a pattern,
which lines matching STALE existed and which were shown, what LFM3 wrote. Usage: python3 replay.py 1 '22|moved' 'march 14|14th'"""
import json, sys, re
sys.path.insert(0, '.'); sys.path.insert(0, '../whiteboard')
import notes_search as ns
wb = ns.wb
STALE = sys.argv[3] if len(sys.argv) > 3 else 'march 14|14th'
chat = int(sys.argv[1]); pat = re.compile(sys.argv[2], re.I)
data = {d['id']: d for d in json.load(open('../whiteboard/data.json'))}
d = data[chat]; res = json.load(open(f'hf-4a/chat-{chat}.json'))
msgs = d['messages']; users = [i for i, m in enumerate(msgs) if m['role'] == 'user']
lines, touched = [], []
for n, i in enumerate(users):
    reply = msgs[i+1]['content'] if i+1 < len(msgs) and msgs[i+1]['role'] == 'assistant' else '(no reply)'
    q = msgs[i]['content'] + ' ' + ' '.join(reply.split()[:60])
    shown = ns.related(lines, touched, q)
    e = res['note_log'][n]
    if pat.search(msgs[i]['content']) or pat.search(reply[:400]):
        print(f'=== turn {n}: USER: {msgs[i]["content"][:300]}')
        print('--- read_notes showed:')
        for k in shown: print(f'  {k+1}. {lines[k]}')
        stale = [k+1 for k, l in enumerate(lines) if l and re.search(STALE, l, re.I)]
        print('--- all live lines mentioning the 14th:', stale, '| shown:', [k for k in stale if k-1 in shown])
        print('--- model wrote:', e['out'][:500].replace('\n', ' | '))
        print('--- ops:', e['ops'])
    _, said, calls = wb.parse_output(e['out'] if '</think>' in e['out'] else '</think>' + e['out'])
    ns.apply_native(lines, touched, calls)
assert [l for l in lines] == res['notes'], 'replay diverged'
print('replay matches the saved notes')
