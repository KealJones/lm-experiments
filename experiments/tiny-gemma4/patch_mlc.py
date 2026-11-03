"""Make the installed mlc_llm build Gemma 4 text-only when the packaged config says "text_only": true.

MLC's gemma4 model always builds E2B's audio tower, its projector and an "audio" input/adapter in the WebLLM
artifact, and its loader expects those weights. Tiny Gemma 4 dropped audio (and vision) in the cut, and its
hidden width is 1024, not E2B's 1536, so E2B's audio projector wouldn't fit anyway. This edits the installed
package in place (text replacement, each one checked) so a text_only config:
  - skips the audio preprocessor, tower and embedder in Gemma4ForConditionalGeneration
  - drops "audio_embed" from the exported functions
  - leaves the audio input and adapter out of the artifact's chat task and generation program
  - skips the loader's generated audio parameters

Written against mlc-llm commit 44fd06d (2026-10-30). If a replacement no longer matches, it stops and says which.
"""
import os, sys

if os.environ.get("MLC_GEMMA4_DIR"):                         # a checkout, for testing the patch without mlc_llm
    root = os.environ["MLC_GEMMA4_DIR"]
else:
    import mlc_llm
    root = os.path.join(os.path.dirname(mlc_llm.__file__), "model", "gemma4")

def patch(fname, edits):
    path = os.path.join(root, fname)
    src = open(path).read()
    for old, new in edits:
        if new in src:
            continue
        if src.count(old) != 1:
            sys.exit(f"patch_mlc: {fname}: expected one match for {old[:60]!r}, found {src.count(old)}")
        src = src.replace(old, new)
    open(path, "w").write(src)
    print("patched", fname)

patch("gemma4_config.py", [
    ("        self.text_config = Gemma4TextConfig.from_dict(text_dict)\n",
     "        self.text_config = Gemma4TextConfig.from_dict(text_dict)\n"
     "        self.text_only = bool(self.kwargs.get(\"text_only\", False))\n"),
])

patch("gemma4_model.py", [
    ("        self.audio_preprocessor = Gemma4AudioFeatureExtractor(config.audio_config)\n"
     "        self.audio_tower = Gemma4AudioModel(config.audio_config)\n"
     "        self.embed_audio = Gemma4MultimodalEmbedder(config.audio_config, config.text_config)\n",
     "        if not getattr(config, \"text_only\", False):\n"
     "            self.audio_preprocessor = Gemma4AudioFeatureExtractor(config.audio_config)\n"
     "            self.audio_tower = Gemma4AudioModel(config.audio_config)\n"
     "            self.embed_audio = Gemma4MultimodalEmbedder(config.audio_config, config.text_config)\n"),
    ("        return nn.spec.ModuleSpec.from_raw(mod_spec, self)\n",
     "        if getattr(self.config, \"text_only\", False):\n"
     "            mod_spec.pop(\"audio_embed\", None)\n"
     "        return nn.spec.ModuleSpec.from_raw(mod_spec, self)\n"),
    ("def gemma4_artifact_tasks(config: Gemma4Config):\n    return {",
     "def gemma4_artifact_tasks(config: Gemma4Config):\n"
     "    if getattr(config, \"text_only\", False):\n"
     "        return {\"chat.completions\": {\"executor\": \"generation\", \"inputs\": {\"text\": {\"processor\": \"tokenizer\"}}, \"output\": \"text\"}}\n"
     "    return {"),
    ("def gemma4_artifact_programs(_config: Gemma4Config):\n    return {",
     "def gemma4_artifact_programs(_config: Gemma4Config):\n"
     "    if getattr(_config, \"text_only\", False):\n"
     "        return {\"generation\": {\"kind\": \"token_generation\", \"exports\": {\"embed_tokens\": \"embed\", "
     "\"prefill_tokens\": \"prefill_tokens\", \"decode_tokens\": \"decode_tokens\", \"create_kv_cache\": \"create_tir_paged_kv_cache\"}, \"adapters\": {}}}\n"
     "    return {"),
])

patch("gemma4_loader.py", [
    ("    for name, value in gemma4_audio_generated_parameters(model_config.audio_config).items():\n",
     "    audio_params = {} if getattr(model_config, \"text_only\", False) else gemma4_audio_generated_parameters(model_config.audio_config)\n"
     "    for name, value in audio_params.items():\n"),
])
print("text-only patch applied")
