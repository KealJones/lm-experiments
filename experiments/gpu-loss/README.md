# GPU loss and recovery: what happens when a phone browser takes the GPU away

**Question (Keal, 2026-11-12):** Safari on iOS 27 kills WebGPU work that runs too long (a 3-second watchdog per
command buffer, from the WebKit commit "Long running command buffers can hang the system"; it isn't in the release
notes) and then may refuse to give the page a GPU again. What exactly is the limit, does splitting work into small
submits avoid it, what does the browser say when it takes the GPU, and how long until it gives one back? This decides
how a custom LFM3 runtime should chunk prefill and recover from losing the GPU.

## Setup

- **The page:** [gpu-loss](https://kealjones.com/lm-experiments/demos/gpu-loss/). It times a busy-loop compute shader
  on this GPU, then:
  1. runs one job of 0.5 s, 1 s, 1.5 s … 10 s until the GPU is lost (the time limit);
  2. runs 6 s of work as 60 pieces of 0.1 s: one submit each (waited for), all submitted at once, then all in one
     submit (is the limit per submit, per queue, or per piece?);
  3. a 15 s job, to lose the GPU on purpose; and a control that calls `device.destroy()` instead.
- **After a loss** it logs the loss reason and message, every `uncapturederror`, what the old adapter does, then asks
  for a new adapter instantly and on a schedule for 10 minutes (plus the software fallback adapter every fourth try),
  and calls the GPU back only when a known-answer job reads back right. "Reload and check" reloads and asks again
  from a fresh page. Everything is written to `localStorage` as it happens, so a crash keeps the log.
- **Checked:** headless Chrome on SwiftShader (2026-11-12): destroy → lost "destroyed" → working GPU again in 3 ms;
  the old adapter refuses (`adapter is "consumed"`); chunking survives all three ways; a reload gets a GPU.

## Results (iPhone 16, Safari 27.2 / iOS 27, 2026-11-12, first version of the page)

**Two different kinds of GPU loss on the iPhone: a single long job loses the device but the page gets a working GPU
back in ~13 ms; ~3 s of back-to-back queued work loses it with "destroyed" and the page gets no GPU at all until it
reloads.**

| What ran | What happened | Loss reason / message | Back after |
|---|---|---|---|
| One dispatch, ramped up (run 1) | lost right after a job that took 2.05 s wall time | "unknown" / empty | 12 ms, no reload |
| One dispatch, ramped up (run 2) | lost right after a job that took 1.83 s wall time | "unknown" / empty | 14 ms, no reload |
| 60 × 0.1 s submits, each waited for | fine, 6.08 s total | | |
| 60 × 0.1 s submits, all queued at once | lost 3.16 s in | "destroyed" / empty (the page never destroyed it) | never: `requestAdapter` returned null 26 times over 210 s, the fallback adapter too; a reload got a GPU at once |
| `device.destroy()` (control) | lost | "destroyed" / empty | 1 ms, no reload |

**What it says:**

- **Safari tells the page nothing.** Every loss message was empty; the reason was "unknown" or "destroyed". A refused
  adapter is just `null`. An empty-message `GPUValidationError` follows each loss. The only way to learn the rules is
  to measure them.
- **Waiting for each small submit kept the GPU alive through 6 s of work.** Queueing the same pieces without waiting
  died at ~3 s, so the limit looks like continuous GPU busy time, not the size of one submit. A runtime has to await
  each chunk, not just split it.
- **The queued loss is the dangerous one:** the page was locked out of WebGPU until a reload. A runtime that hits it
  has to save its state, reload and restore (or drop to the CPU), not wait.
- **The single-dispatch numbers aren't trustworthy yet.** Wall times didn't track the work asked for (a "1.5 s" job took
  0.51 s; after the reload a "15 s" job finished in 0.53 s), and the page blamed each loss on the job after the one
  that caused it. Either the GPU's speed swings a lot, or Safari cuts long shader loops short without saying so. The
  page now checks each job's answer on the CPU, reads GPU-side time from timestamp queries, and attributes a loss
  seen before a submit to the job before it. Rerun test 1 and test 2 to settle it.
