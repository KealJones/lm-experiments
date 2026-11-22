# WebGPU on a rented GPU: can Squiggle's evals run Tilde off the phone?

Squiggle's evals (KealJones/squiggle `tests/eval`) drive the real app in headless Chromium. With LFM3 1.7B on Tilde,
which needs WebGPU, they have so far run only on an iPhone through the phone relay: one case at a time, one run per
case, and only while the phone stays awake. This asks whether a Hugging Face GPU job can do it instead.

One `t4-small` job (`hf/queue/webgpu-smoke-2.json`) runs `tests/eval/hf-gpu-smoke.sh` from the squiggle branch
`gpu-smoke`:

1. `nvidia-smi` and `vulkaninfo`: is there a GPU, and does Vulkan see it? Hugging Face reserves
   `NVIDIA_DRIVER_CAPABILITIES` (webgpu-smoke-1 was refused for setting it), so when the driver's Vulkan libraries
   aren't mounted the script copies them in from the same driver version's NVIDIA installer.
2. `tests/eval/gpu-probe.mjs`: four sets of Chrome switches, each reporting the WebGPU adapter and a timed
   1024² matmul. On a box with no GPU it reports SwiftShader at about 6.5 s per matmul.
3. If one set gets the real GPU: deliberation case 1 ("Tell me about Olivia Rodrigo") through the real app on
   Tilde, with the same weights as the phone (Liquid's 4-bit QAD GGUF), timed.

Spend: 45 min cap on a T4, so at most $0.30.

## Results

Pending: `hf-2/` gets the job's log, the probe output and the case result.
