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

**Runs and spend.** `whiteboard-1` (vLLM, a10g-small): died at model load, pip vLLM has no native LFM3 and its generic
fallback can't run the conv layers, $0.08. `whiteboard-2` (llama.cpp built in the job, L4): ran but far too slow, the
loop waited for the slowest of 16 chats every round, $0.76 (its pilot is used below). `whiteboard-3` (one thread per
chat, A100): hit its 60 min cap with 693 of 834 turns replayed; 3 of 16 notes chats (11, 12, 16) reached the final
question. **Total $3.34.**

### The notes mostly weren't written, because LFM3 ran out of output while thinking

Of 693 end-of-turn nudges ([hf-3/ANALYSIS.md](hf-3/ANALYSIS.md)):

| what happened | turns | share |
|---|---|---|
| ran out of output (Squiggle's 1,536-token cap) while still thinking | 492 | 71% |
| finished thinking, then ended its turn without a call | 137 | 20% |
| wrote the file | 61 | 9% |

50 of the 61 writes happen in a chat's first 10 turns. LFM3's thinking restates the whole notes file, then drafts
the whole new version, then plans a `cat > /home/notes.md <<EOF` rewrite. Once the file is ~150 words, that thinking
alone fills the 1,536 tokens and the write never happens. It never once decided there was nothing new. The other
20% is the pilot's pattern: it drafts the file, says "Let's do it.", and ends the turn.

So the throwaway corrections this experiment is about mostly never reached the file: in the chats where they had
been said by the cut-off, 12 of 36 answer-key facts were in the notes (tests 1-12, at the point each chat reached).

**When it did write, the notes were good.** Clean, organised, in its own words. In test 12 it made its own
"Writing Rules (non-negotiable)" section for the team's error-envelope and no-new-dependencies rules. The orders-table
spec, said later, never got in.

### Final answers (graded blind, [hf-3/GRADES.md](hf-3/GRADES.md))

| | tests 1-12 | tests 13-16 (last message only) |
|---|---|---|
| LFM3, full history (no 4K limit) | 5/12 pass, mean 5.5 | 4/4, 9.8 |
| LFM3, last 2 exchanges only (+ `find`) | 2/12, 2.5 | 3/4, 8.0 |
| LFM3, last 2 exchanges + its notes | 1/2 reached (11 pass, 12 fail) | 1/1 (16 pass) |
| *for reference, context-packets:* Haiku full history | 11/12 | - |

- Full history doesn't save LFM3 here: 3 of its 7 misses are the same output cap (see the correction below) (tests 4 and 12 cut off mid-thinking,
  test 10 cut off on day 2 of the plan), and the rest are reasoning misses (test 8 says to sign the carpeted
  apartment; test 3 imports a non-guest's no-garlic rule).
- Window-only passed test 6 by calling `find`, which pulled the corrected run table from the earlier turns.
- Test 11 passes everywhere because the chat ends with the assistant restating every number (a known generator quirk).

### Correction: this run did not use Squiggle's real output limits

`agent.js` asks for 1,536 output tokens (`MAX_OUTPUT`, a reply reserve in a 4K window since phase 1), and this
harness used that. But LFM3 runs through `engine-wllama.js`'s conversation on both builds (the WebLLM build imports
it too), and that engine **clamps every reply to 1,024 tokens** and gives small models a **400-token thinking budget**
(`engine.js` `generationFor`): past 400 tokens Squiggle closes the think block with "[Squiggle stopped the thinking
at its 400-token budget and asked for the answer.]" and lets the model continue, so it has to act. That budget exists
because of exactly the failure above ("a 0.6B model thought until the output cap and never answered").

So the 71% ran-out-while-thinking number is this harness's, not Squiggle's. On the phone, LFM3 would have been
stopped at 400 tokens of thinking and pushed to write. Whether it then writes good notes is what the next run tests.

## Next

The idea isn't tested yet: the model barely wrote. A fair version needs the writes to be cheap:

0. **Squiggle's real limits first:** a 1,024-token reply and the 400-token thinking budget with the forced
   continuation, as `engine-wllama.js` does. This is the faithful rerun of this exact setup.
1. **Edit, don't rewrite.** Show the notes with line numbers (`cat -n`) and ask for one-line edits: `echo '- …' >>`
   to add, `sed -i 'Ns/…/…/'` to change. Then the thinking doesn't need to restate the file.
2. **Thinking off for the note step** (LFM3's `<think></think>`), on for the answer. A note is a reflex, not a puzzle.
3. Keep the 4K window, but give answers the room the reply budget allows, and log how often the cap hits.

On an L4 with thinking off for notes this should be ~45 min including the image pull and build: about $0.60.
