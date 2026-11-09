"""Trace a small LFM3 (same layer pattern, tiny dims) through mlc_llm's model export, the loader mapping
and (optionally) the quantized export, without weights or a GPU. Catches shape/op/API errors before a
paid build. `python trace_test.py [--quantize]`."""

import sys

from tvm import relax

from mlc_llm.model.lfm3.lfm3_loader import huggingface
from mlc_llm.model.lfm3.lfm3_model import Lfm3Config, Lfm3ForCausalLM

LAYER_TYPES = ["conv", "conv", "full_attention", "conv", "sliding_attention", "conv", "full_attention", "conv"]


def main():
    config = Lfm3Config.from_dict(
        {
            "hidden_size": 64,
            "intermediate_size": 96,
            "num_hidden_layers": len(LAYER_TYPES),
            "num_attention_heads": 4,
            "num_key_value_heads": 2,
            "head_dim": 16,
            "vocab_size": 256,
            "layer_types": LAYER_TYPES,
            "conv_L_cache": 7,
            "sliding_window": 256,
            "max_position_embeddings": 4096,
            "prefill_chunk_size": 1024,
            "dtype": "bfloat16",
        }
    )
    assert config.sliding_window_size == -1
    assert config.prefill_chunk_size == 256, config.prefill_chunk_size
    assert config.num_attention_layers == 3 and config.num_conv_layers == 5
    assert config.rotary_dim("full_attention") == 8 and config.rotary_dim("sliding_attention") == 16

    model = Lfm3ForCausalLM(config)
    model.to("float16")
    mod, named_params = model.export_tvm(spec=model.get_default_spec())
    names = [n for n, _ in named_params]
    print(len(names), "params, e.g.", names[:3], names[-3:])
    assert "model.layers.2.self_attn.gate_proj.weight" in names
    assert "model.layers.0.conv.conv1d_weight" in names
    assert "model.layers.0.post_ffn_norm.weight" in names
    funcs = [gv.name_hint for gv in mod.functions]
    for f in ["embed", "batch_prefill", "batch_decode", "create_paged_kv_cache", "create_rnn_state"]:
        assert f in funcs, f
    mod.show() if "--show" in sys.argv else None

    cache_calls = []

    def collect(expr):
        if (
            isinstance(expr, relax.Call)
            and getattr(expr.op, "name", None) == "relax.call_pure_packed"
            and getattr(expr.args[0], "global_symbol", None) == "mlc.create_paged_kv_cache_generic"
        ):
            cache_calls.append(expr)

    relax.analysis.post_order_visit(mod["create_paged_kv_cache"].body, collect)
    assert len(cache_calls) == 1
    args = cache_calls[0].args
    kinds = [k.value for k in args[1]]
    assert kinds == ["mha", "mha_sliding", "mha"], kinds
    assert int(args[2].values[-1]) == 256
    print("kv cache: kinds", kinds, "window", int(args[2].values[-1]))

    from mlc_llm.quantization import QUANTIZATION

    mapping = huggingface(config, QUANTIZATION["q0f16"])
    hf_names = sorted({src for srcs in mapping.param_map.values() for src in srcs})
    expect = {
        "model.embed_tokens.weight",
        "model.embedding_norm.weight",
        "model.layers.0.conv.conv.weight",
        "model.layers.0.conv.in_proj.weight",
        "model.layers.2.self_attn.q_proj.weight",
        "model.layers.2.self_attn.gate_proj.weight",
        "model.layers.2.self_attn.q_norm.weight",
        "model.layers.2.feed_forward.w1.weight",
        "model.layers.2.post_operator_norm.weight",
    }
    missing = expect - set(hf_names)
    assert not missing, missing
    print(len(hf_names), "HF tensors mapped")

    if "--quantize" in sys.argv:
        quant = QUANTIZATION["q4f16_1"]
        qmodel = quant.quantize_model(Lfm3ForCausalLM(config), __import__("mlc_llm").loader.QuantizeMapping({}, {}), "")
        qmod, qparams = qmodel.export_tvm(spec=qmodel.get_default_spec())
        print(len(qparams), "quantized params")
    print("trace ok")


if __name__ == "__main__":
    main()
