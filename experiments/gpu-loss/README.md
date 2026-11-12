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

## Results

Not run on a phone yet: next, Keal's iPhone 16 in Safari (iOS 27), with Web Inspector attached for console-only errors.
