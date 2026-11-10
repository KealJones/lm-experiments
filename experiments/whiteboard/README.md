# Whiteboard: can LFM3 1.7B keep its own notes well enough to drop the chat history?

Follow-up to [context-packets](../context-packets/). There, a big model read the whole chat and wrote a ~350-word
packet. Retrieval (BM25, embeddings, query rewriters, doc2query) couldn't replace it at that size: the facts that
matter are throwaway corrections ("btw we moved the party") that share no words with the later question.

So this moves the work to write time. Keal's design: a plain whiteboard file the assistant keeps in its own words,
edited with the bash it already has, plus an end-of-turn instruction to update it. No new tools.

## Setup

- **Model:** LFM3 1.7B (`LiquidAI/LFM3-1.7B`), Squiggle's model, thinking on, sampling from Squiggle's engine.js.
- **Prompt:** Squiggle PR 7 (`f987588`) exactly as it renders for LFM3: small-model mode on the bash surface
  (`LITE_SYSTEM_BASH` + the tools-ready line + date), tools `remember, bash, plan, need, find, tool_info` in LFM3's
  XML format. Checked byte for byte against Squiggle's `toolformats/lfm3.js`.
- **Shell:** just-bash from Squiggle's vendor folder, one in-memory filesystem per chat. `man` and `bc` work;
  `curl`, `search`, `wiki`, `git`, `gh`, `node` are stubbed as offline (the original answerers had no web either).
- **Window:** 4K tokens like Squiggle's LFM3 build, max 1,536 out.
- **Replay:** every user turn of the 16 chats, in order. The model sees its last 2 exchanges, the new message, a
  `cat /home/notes.md` it "already ran", the recorded assistant reply, then the end-of-turn note:
  > (Squiggle: Older turns are dropped from your view; /home/notes.md is what you'll have instead. Update it now with
  > anything from this exchange that might be needed later: names, dates, times, places, numbers, plans, decisions,
  > changes, even side comments. Change lines that are out of date instead of adding a second version. Write it in
  > your own words, as your notes. If nothing new came up, leave it as it is.)

  Its own replies are thrown away during replay (the next scripted user turn answers the recorded reply).
- **Arms:** `notes` (last 2 exchanges + notes), `window` (last 2 exchanges only; `find` still searches the earlier
  turns with BM25), `full` (whole chat, no 4K limit: the ceiling).
- **Scoring:** answer-key facts present in the final notes file (same needles as the context-packets retrieval
  check), notes behaviour, and blind grading of the final answers against the context-packets keys.

## Results

- Job `whiteboard-1` (a10g-small, ~5 min, about $0.10): failed. pip vLLM has no native LFM3 and its generic fallback cannot run the conv layers.
- Job `whiteboard-2`: llama.cpp master (native LFM3) built with CUDA in the job, on Liquid's QAD Q4_0 GGUF (the file Squiggle's CPU build loads). l4x1, 75 min cap (at most $1). Pending.
