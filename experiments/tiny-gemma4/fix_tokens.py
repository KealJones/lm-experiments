"""Fix a tiny-Gemma-4 GGUF's special tokens in place (metadata only; weights untouched).

Pruning the vocabulary shifted token ids, and llama.cpp's converter then marked the wrong tokens as control
tokens: <|turn>, <turn|>, <|tool>, <tool|> came out as plain text, so a chat prompt's turn markers were split
into text pieces the model never saw (it echoed the question back), and generation didn't stop at <turn|>.
This sets each special token's type by its text, exactly as in the official Gemma 4 E2B GGUF (unsloth
gemma-4-E2B-it-GGUF), and makes <turn|> the end-of-generation token like there.

    python fix_tokens.py MODEL.gguf
"""
import sys
from gguf import GGUFReader

NORMAL, CONTROL, USER_DEFINED = 1, 3, 4
TYPES = {   # from the official E2B GGUF's tokenizer.ggml.token_type
    '<pad>': CONTROL, '<eos>': NORMAL, '<bos>': CONTROL, '<unk>': CONTROL, '<mask>': CONTROL,
    '<|tool>': CONTROL, '<tool|>': CONTROL, '<|think|>': CONTROL, '<|turn>': CONTROL, '<turn|>': CONTROL,
    '<|tool_call>': USER_DEFINED, '<tool_call|>': USER_DEFINED, '<|tool_response>': USER_DEFINED,
    '<tool_response|>': USER_DEFINED, '<|"|>': USER_DEFINED, '<|channel>': USER_DEFINED, '<channel|>': USER_DEFINED,
    '<|image>': CONTROL, '<|audio>': CONTROL, '<|image|>': CONTROL, '<|audio|>': CONTROL, '<image|>': CONTROL,
    '<audio|>': CONTROL, '<|video|>': CONTROL,
}

path = sys.argv[1]
r = GGUFReader(path, 'r+')
toks, tt = r.fields['tokenizer.ggml.tokens'], r.fields['tokenizer.ggml.token_type']
names = [bytes(toks.parts[i]).decode('utf-8', 'replace') for i in toks.data]
idx = {n: i for i, n in enumerate(names)}
changed = []
for name, want in TYPES.items():
    if name not in idx:
        continue
    cell = tt.parts[tt.data[idx[name]]]
    if int(cell[0]) != want:
        changed.append((name, int(cell[0]), want))
        cell[0] = want
eos = r.fields['tokenizer.ggml.eos_token_id'].parts[-1]
if int(eos[0]) != idx['<turn|>']:
    changed.append(('eos_token_id', int(eos[0]), idx['<turn|>']))
    eos[0] = idx['<turn|>']
r.data.flush() if hasattr(r.data, 'flush') else None
print('fixed', path, changed)
