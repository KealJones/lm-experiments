# Notes search: can LFM3's own notes plus a dumb search be Squiggle's fresh context?

Follow-up to [whiteboard](../whiteboard/) and [context-packets](../context-packets/). Keal's design (voice, 2026-11-10):
the packet for each new message is the last exchange plus the relevant lines of notes the model keeps itself, with
no chat history. Retrieval on the raw chat failed because throwaway corrections share no words with the later
question; the notes are short, clean and written by the model, so maybe a search over them works.

## Setup

- **Model:** LFM3 1.7B, Liquid's QAD Q4_0 GGUF on llama.cpp (native LFM3), same as Squiggle's CPU build.
- **Note pass** (separate from the reply, as it would run while the user reads): its own ~120-token system prompt,
  thinking off, max 200 tokens out. Input: the notes numbered, plus the latest exchange only. Output lines:
  `ADD: <fact> | tags: <plain words> | <kind>`, `CHANGE <n>: ...`, or `NONE`; the harness applies them.
  Tags (plain words someone would use to ask, plus a kind: date, place, money, person, rule, plan, number, other) are
  there to give BM25 something to match without a second model.
- **Packets** (per final question): the last exchange (user message whole, the reply's first 60 words) plus the top
  8 note lines from each of:
  - BM25 on the raw message, with tags / without tags
  - bge-small embeddings (33M parameters, ~35-130 MB)
  - hybrid (reciprocal rank fusion of the two)
  - an LFM3-written search query (thinking off, sees only the last exchange and the new message) into BM25 / hybrid
  - whole notes (ceiling)
- **Answers:** LFM3 with Squiggle PR 7's prompt and its real engine limits (1,024-token reply, 400-token thinking
  budget), handed the packet as the result of a `relevant_context` call it "already made". Arms: whole, BM25, hybrid,
  LFM3 query into BM25.
- **Timing:** every call logs its prompt and output tokens. Phone time is estimated from Keal's iPhone measurements of
  the LFM3 WebLLM build (13.7 tokens/s decode, first word in ~15 s with Squiggle's full prompt; lfm3-mlc README).

## Results

Pending: job `notes-search-1` (l4x1, 60 min cap, at most $0.80).
