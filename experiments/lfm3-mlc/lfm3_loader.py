"""HuggingFace parameter mapping for LFM3 (LiquidAI/LFM3-1.7B, model.safetensors).

HF weight layout (under `model.`):
  conv layers:        model.layers.{i}.conv.in_proj.weight
                      model.layers.{i}.conv.out_proj.weight
                      model.layers.{i}.conv.conv.weight (hidden, 1, kernel)  -> MLC conv.conv1d_weight
  attention layers:   model.layers.{i}.self_attn.{q,k,v}_proj.weight       -> MLC self_attn.c_attn.weight
                      model.layers.{i}.self_attn.o_proj.weight
                      model.layers.{i}.self_attn.{q,k}_norm.weight
                      model.layers.{i}.self_attn.gate_proj.weight (heads, hidden)
  per layer:          model.layers.{i}.{operator_norm,ffn_norm,post_operator_norm,post_ffn_norm}.weight
                      model.layers.{i}.feed_forward.{w1,w3}.weight -> MLC feed_forward.gate_up_proj
                      model.layers.{i}.feed_forward.w2.weight      -> MLC feed_forward.down_proj
  top level:          model.embed_tokens.weight
                      model.embedding_norm.weight                  -> MLC model.norm.weight
  lm_head is tied to embed_tokens (tie_word_embeddings=True).

LFM3 RMSNorm is standard (weight * normed), so weights load 1:1 with no +1 offset.
"""

import functools

import numpy as np

from mlc_llm.loader import ExternMapping
from mlc_llm.quantization import Quantization

from .lfm3_model import ATTENTION_LAYER_TYPES, Lfm3Config, Lfm3ForCausalLM


def huggingface(model_config: Lfm3Config, quantization: Quantization) -> ExternMapping:
    model = Lfm3ForCausalLM(model_config)
    if quantization is not None:
        model.to(quantization.model_dtype)

    _, _named_params, _ = model.export_tvm(
        spec=model.get_default_spec(),
        allow_extern=True,
    )
    named_parameters = dict(_named_params)

    mapping = ExternMapping()

    def _astype(dtype):
        return functools.partial(lambda x, dtype: x.astype(dtype), dtype=dtype)

    for i, ltype in enumerate(model_config.layer_types):
        if ltype in ATTENTION_LAYER_TYPES:
            attn = f"model.layers.{i}.self_attn"
            mlc_name = f"{attn}.c_attn.weight"
            if mlc_name in named_parameters:
                dtype = named_parameters[mlc_name].dtype
                mapping.add_mapping(
                    mlc_name,
                    [f"{attn}.q_proj.weight", f"{attn}.k_proj.weight", f"{attn}.v_proj.weight"],
                    functools.partial(
                        lambda q, k, v, dtype: np.concatenate([q, k, v], axis=0).astype(dtype),
                        dtype=dtype,
                    ),
                )
        else:
            mlc_name = f"model.layers.{i}.conv.conv1d_weight"
            if mlc_name in named_parameters:
                dtype = named_parameters[mlc_name].dtype
                mapping.add_mapping(mlc_name, [f"model.layers.{i}.conv.conv.weight"], _astype(dtype))
            mlc_name = f"model.layers.{i}.conv.conv1d_bias"
            if mlc_name in named_parameters:
                dtype = named_parameters[mlc_name].dtype
                mapping.add_mapping(mlc_name, [f"model.layers.{i}.conv.conv.bias"], _astype(dtype))

        ff = f"model.layers.{i}.feed_forward"
        gate_up = f"{ff}.gate_up_proj.weight"
        if gate_up in named_parameters:
            dtype = named_parameters[gate_up].dtype
            mapping.add_mapping(
                gate_up,
                [f"{ff}.w1.weight", f"{ff}.w3.weight"],
                functools.partial(
                    lambda w1, w3, dtype: np.concatenate([w1, w3], axis=0).astype(dtype),
                    dtype=dtype,
                ),
            )
        down = f"{ff}.down_proj.weight"
        if down in named_parameters:
            dtype = named_parameters[down].dtype
            mapping.add_mapping(down, [f"{ff}.w2.weight"], _astype(dtype))

    if "model.norm.weight" in named_parameters:
        dtype = named_parameters["model.norm.weight"].dtype
        mapping.add_mapping("model.norm.weight", ["model.embedding_norm.weight"], _astype(dtype))

    # Everything else (embed_tokens, the four per-layer norms, q/k_norm, o_proj, gate_proj, conv in/out_proj)
    # maps 1:1 with identical names.
    for mlc_name, mlc_param in named_parameters.items():
        if mlc_name not in mapping.param_map:
            mapping.add_mapping(mlc_name, [mlc_name], _astype(mlc_param.dtype))

    return mapping
