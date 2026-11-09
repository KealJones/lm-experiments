"""
LFM3 (Liquid AI, LiquidAI/LFM3-1.7B) for mlc-llm: a hybrid decoder stack of

  - `conv` layers: the LIV double-gated short causal convolution (depthwise, kernel = conv_L_cache = 7),
    whose last (kernel - 1) gated inputs live in a per-layer RNNState ring buffer next to the KV cache
    (the Qwen3.5 / Kiln LFM2 hybrid pattern: no custom TVM operator);
  - `full_attention` layers: GQA with per-head QK-RMSNorm, a per-head sigmoid output gate, and RoPE on the
    first half of each head only (theta 1e6, "zero-tail" partial rotation: pairs (i, i+64) for i < 32);
  - `sliding_attention` layers: the same block with full-head RoPE (theta 1e4) and a 256-token window,
    which the PagedKVCache applies per layer ("mha_sliding", as mlc-llm does for Gemma 3).

Each block is sandwiched: RMSNorm -> op -> RMSNorm -> residual, RMSNorm -> FFN -> RMSNorm -> residual.
RoPE is computed in the model (RopeMode.NONE in the cache) because the two attention kinds use different
thetas and the global layers rotate only half the head. Written against mlc-llm 44fd06d (2026-10-30) /
TVM e345029 (the toolchain behind WebLLM 0.2.87's own model libraries); the tirx import also works with
the Sep 2026 nightly wheels (`from tvm import tirx`) so the trace can be checked without the full build.
Started from NakliTechie/mlc-llm's lfm2 (Kiln) port.
"""

import dataclasses
from typing import Any, Dict, List, Optional, Tuple  # noqa: UP035

import numpy as np
from tvm import relax as R
from tvm import te
from tvm.relax.frontend import nn
from tvm.relax.frontend.nn import Tensor, op

try:  # mlc-llm >= 2026-10-30 (TIRx split)
    from tvm_tirx import tirx
except ImportError:  # the Sep 2026 nightly wheels
    from tvm import tirx

from mlc_llm import op as op_ext
from mlc_llm.nn import PagedKVCache, RopeMode
from mlc_llm.nn.rnn_state import RNNState
from mlc_llm.support import logging
from mlc_llm.support.config import ConfigBase
from mlc_llm.support.style import bold

logger = logging.getLogger(__name__)

ATTENTION_LAYER_TYPES = ("full_attention", "sliding_attention")


@dataclasses.dataclass
class Lfm3Config(ConfigBase):
    """Configuration of an LFM3 model (HF config.json)."""

    hidden_size: int = 2048
    intermediate_size: int = 7680
    num_attention_heads: int = 16
    num_hidden_layers: int = 24
    num_key_value_heads: int = 4
    norm_eps: float = 1e-5
    vocab_size: int = 128_000
    head_dim: int = 0
    tie_word_embeddings: bool = True
    conv_L_cache: int = 7
    conv_bias: bool = False
    use_sandwich_norm: bool = True
    layer_types: Optional[List[str]] = None  # noqa: UP006,UP007
    sliding_window: int = 256
    rope_parameters: Optional[Dict[str, Any]] = None  # noqa: UP006,UP007
    # Runtime
    context_window_size: int = 0
    prefill_chunk_size: int = 0
    sliding_window_size: int = -1
    tensor_parallel_shards: int = 1
    dtype: str = "float32"
    max_batch_size: int = 1
    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)  # noqa: UP006

    def __post_init__(self):
        if self.head_dim == 0:
            assert self.hidden_size % self.num_attention_heads == 0
            self.head_dim = self.hidden_size // self.num_attention_heads
        if self.layer_types is None:
            self.layer_types = [
                "full_attention" if i % 4 == 2 else "sliding_attention" if i % 4 == 0 and i > 0 else "conv"
                for i in range(self.num_hidden_layers)
            ]
        assert len(self.layer_types) == self.num_hidden_layers, (
            f"layer_types length {len(self.layer_types)} != num_hidden_layers {self.num_hidden_layers}"
        )
        bad = [t for t in self.layer_types if t not in (*ATTENTION_LAYER_TYPES, "conv")]
        assert not bad, f"unknown layer types {bad}"
        if self.rope_parameters is None:
            self.rope_parameters = {
                "full_attention": {"rope_type": "default", "rope_theta": 1_000_000.0, "partial_rotary_factor": 0.5},
                "sliding_attention": {"rope_type": "default", "rope_theta": 10_000.0},
            }
        for kind in ATTENTION_LAYER_TYPES:
            if kind in self.layer_types:
                params = self.rope_parameters.get(kind)
                assert params is not None, f"rope_parameters has no entry for {kind}"
                assert params.get("rope_type", "default") == "default", (
                    f"only default RoPE is supported, got {params['rope_type']} for {kind}"
                )
        if self.context_window_size == 0:
            for name in ["max_position_embeddings", "max_sequence_length"]:
                if name in self.kwargs:
                    self.context_window_size = self.kwargs.pop(name)
                    logger.info(
                        "%s not found in config.json. Falling back to %s (%d)",
                        bold("context_window_size"),
                        bold(name),
                        self.context_window_size,
                    )
                    break
            else:
                raise ValueError(
                    "Unable to determine the maximum sequence length, because none of "
                    "`context_window_size`, `max_position_embeddings` or `max_sequence_length` is "
                    "provided in `config.json`."
                )
        if self.prefill_chunk_size == 0 or self.prefill_chunk_size > self.context_window_size:
            self.prefill_chunk_size = min(self.context_window_size, 2048)
        # The KV cache applies the window per layer; the model-level sliding window stays off so runtimes
        # do not slide the whole cache. Within a prefill chunk the ragged kernel only masks causally, so the
        # chunk must not be longer than the window (mlc-llm's Gemma 3 does the same).
        self.sliding_window_size = -1
        if "sliding_attention" in self.layer_types and self.prefill_chunk_size > self.sliding_window:
            logger.info(
                "Clamping LFM3 %s from %d to its sliding window %d",
                bold("prefill_chunk_size"),
                self.prefill_chunk_size,
                self.sliding_window,
            )
            self.prefill_chunk_size = self.sliding_window

    @property
    def num_attention_layers(self) -> int:
        return sum(1 for t in self.layer_types if t in ATTENTION_LAYER_TYPES)

    @property
    def num_conv_layers(self) -> int:
        return self.num_hidden_layers - self.num_attention_layers

    def rope_theta(self, layer_type: str) -> float:
        return float(self.rope_parameters[layer_type]["rope_theta"])

    def rotary_dim(self, layer_type: str) -> int:
        """Head dims that rotate: the first partial_rotary_factor * head_dim (zero-tail layout)."""
        factor = float(self.rope_parameters[layer_type].get("partial_rotary_factor", 1.0))
        return 2 * (int(factor * self.head_dim) // 2)


# ============================================================================
# Sub-modules
# ============================================================================


class Lfm3Embedding(nn.Embedding):
    """Embedding that doubles as a tied lm_head."""

    def lm_head_forward(self, x: nn.Tensor):
        weight = nn.op.permute_dims(self.weight)
        return nn.op.matmul(x, weight, out_dtype="float32")


class Lfm3MLP(nn.Module):
    """SwiGLU FFN (fused gate+up). HF: w2(silu(w1(x)) * w3(x))."""

    def __init__(self, config: Lfm3Config):
        self.intermediate_size = config.intermediate_size // config.tensor_parallel_shards
        self.gate_up_proj = nn.Linear(config.hidden_size, 2 * self.intermediate_size, bias=False)
        self.down_proj = nn.Linear(self.intermediate_size, config.hidden_size, bias=False)

    def forward(self, x: Tensor):
        concat_x1_x2 = self.gate_up_proj(x)
        x1, x2 = op.split(concat_x1_x2, 2, axis=-1)
        return self.down_proj(op.silu(x1) * x2)


class Lfm3Attention(nn.Module):
    """GQA with per-head QK-RMSNorm (before RoPE), RoPE in float32 and a per-head sigmoid output gate.

    Q/K/V are fused into `c_attn`; the KV cache gets already-rotated q and k (RopeMode.NONE) because the
    global layers rotate only the first half of each head and the two layer kinds use different thetas.
    """

    def __init__(self, config: Lfm3Config, layer_type: str):
        self.head_dim = config.head_dim
        self.num_attention_heads = config.num_attention_heads // config.tensor_parallel_shards
        self.num_key_value_heads = config.num_key_value_heads // config.tensor_parallel_shards
        self.norm_eps = config.norm_eps
        self.rope_theta = config.rope_theta(layer_type)
        self.rotary_dim = config.rotary_dim(layer_type)

        self.c_attn = nn.Linear(
            in_features=config.hidden_size,
            out_features=(self.num_attention_heads + 2 * self.num_key_value_heads) * self.head_dim,
            bias=False,
        )
        self.o_proj = nn.Linear(self.num_attention_heads * self.head_dim, config.hidden_size, bias=False)
        self.gate_proj = nn.Linear(config.hidden_size, self.num_attention_heads, bias=False)
        self.q_norm = nn.RMSNorm(config.head_dim, -1, config.norm_eps, bias=False)
        self.k_norm = nn.RMSNorm(config.head_dim, -1, config.norm_eps, bias=False)

    def _rope(self, qkv: Tensor, positions: Tensor) -> Tensor:
        """RoPE on the q and k heads of the fused qkv, computed in float32 like the reference.

        HF's Lfm3RotaryEmbedding keeps the frequency progression of the full head dim and zeroes the tail:
        with rotate_half pairing dim i with i + d/2, the pair (i, i + d/2) rotates by
        pos / theta^(2i/d) when i < rotary_dim/2 and stays put otherwise.
        """
        d, half = self.head_dim, self.head_dim // 2
        num_rotated_heads = self.num_attention_heads + self.num_key_value_heads
        theta, rotary_half = self.rope_theta, self.rotary_dim // 2

        def _compute(qkv: te.Tensor, positions: te.Tensor):
            seq_len = qkv.shape[1]

            def _value(b: tirx.Var, s: tirx.Var, h: tirx.Var, i: tirx.Var):
                x = qkv[b, s, h, i]
                j = i % half
                freq = positions[b * seq_len + s].astype("float32") / tirx.power(
                    theta, (j * 2).astype("float32") / tirx.const(d, "float32")
                )
                rotated = tirx.if_then_else(i < half, -qkv[b, s, h, i + half], qkv[b, s, h, i - half])
                cos = tirx.cos(freq) * x.astype("float32")
                sin = tirx.sin(freq) * rotated.astype("float32")
                rotate = tirx.And(h < num_rotated_heads, j < rotary_half)
                return tirx.if_then_else(rotate, (cos + sin).astype(qkv.dtype), x)

            return te.compute(qkv.shape, _value, name="lfm3_rope")

        return op.tensor_expr_op(_compute, "lfm3_rope", [qkv, positions])

    def forward(self, hidden_states: Tensor, paged_kv_cache: PagedKVCache, positions: Tensor, layer_id: int):
        d, h_q, h_kv = self.head_dim, self.num_attention_heads, self.num_key_value_heads
        b, s, _ = hidden_states.shape
        qkv = self.c_attn(hidden_states)
        qkv = op.reshape(qkv, (b, s, h_q + h_kv + h_kv, d))
        q, k, v = op.split(qkv, [h_q, h_q + h_kv], axis=2)
        q = self.q_norm(q)
        k = self.k_norm(k)
        qkv = op.concat([q, k, v], dim=2)
        qkv = self._rope(qkv, positions)
        output = paged_kv_cache.attention_with_fused_qkv(layer_id, qkv, h_q, sm_scale=d**-0.5)
        gate = op.sigmoid(self.gate_proj(hidden_states))  # (b, s, h_q)
        output = output * op.reshape(gate, (b, s, h_q, 1))
        output = op.reshape(output, (b, s, h_q * d))
        return self.o_proj(output)


class Lfm3ShortConv(nn.Module):
    """The LIV double-gated short causal convolution.

    in_proj(x) -> [B, C, x] (each `hidden`); Bx = B * x; depthwise causal Conv1d (kernel = conv_L_cache,
    no activation); y = C * conv_out; out_proj. The conv reads the last (kernel - 1) `Bx` positions from
    a per-layer RNNState ring buffer and writes the new last (kernel - 1) back.
    """

    def __init__(self, config: Lfm3Config, conv_layer_idx: int):
        self.conv_layer_idx = conv_layer_idx  # index among conv layers only (RNNState layer id)
        self.hidden_size = config.hidden_size
        self.kernel_size = config.conv_L_cache
        self.dtype = config.dtype

        self.in_proj = nn.Linear(config.hidden_size, 3 * config.hidden_size, bias=config.conv_bias)
        self.out_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=config.conv_bias)
        # Depthwise causal conv kernel (channels, 1, kernel): an nn.Parameter, so it stays in the model
        # dtype (not group-quantized).
        self.conv1d_weight = nn.Parameter((config.hidden_size, 1, config.conv_L_cache))
        if config.conv_bias:
            self.conv1d_bias = nn.Parameter((config.hidden_size,))
        else:
            self.conv1d_bias = None

    def forward(self, hidden_states: Tensor, state: RNNState) -> Tuple[Tensor, RNNState]:  # noqa: UP006
        b, _, _ = hidden_states.shape
        h = self.hidden_size
        layer_idx = self.conv_layer_idx

        bcx = self.in_proj(hidden_states)
        b_gate, c_gate, x_conv = op.split(bcx, 3, axis=-1)
        bx = b_gate * x_conv

        conv_state = state.get(layer_idx, 0, (b, self.kernel_size - 1, h), self.dtype)
        conv_out, new_conv_state = self._causal_conv1d_with_state(bx, conv_state)
        state = state.set(layer_idx, 0, new_conv_state)

        y = c_gate * conv_out
        return self.out_proj(y), state

    def _causal_conv1d_with_state(self, x: Tensor, conv_state: Tensor) -> Tuple[Tensor, Tensor]:  # noqa: UP006
        """Depthwise causal Conv1D over [conv_state || x]; returns (conv_out, new_state)."""
        kernel_size = self.kernel_size

        def _te_update_conv_state(old_state: te.Tensor, x_in: te.Tensor):
            ks_minus_1 = old_state.shape[1]
            seq = x_in.shape[1]
            return te.compute(
                old_state.shape,
                lambda bi, ti, di: tirx.if_then_else(
                    seq + ti < ks_minus_1,
                    old_state[bi, seq + ti, di],
                    x_in[bi, seq + ti - ks_minus_1, di],
                ),
                name="update_conv_state",
            )

        new_conv_state = op.tensor_expr_op(_te_update_conv_state, "update_conv_state", [conv_state, x])

        def _te_depthwise_conv(state: te.Tensor, x_in: te.Tensor, weight: te.Tensor):
            ks_m1 = state.shape[1]
            seq = x_in.shape[1]
            kk = te.reduce_axis((0, kernel_size), name="kk")
            return te.compute(
                (x_in.shape[0], seq, x_in.shape[2]),
                lambda bi, si, di: te.sum(
                    tirx.if_then_else(
                        si + kk < ks_m1,
                        state[bi, si + kk, di],
                        x_in[bi, si + kk - ks_m1, di],
                    )
                    * weight[di, 0, kk],
                    axis=kk,
                ),
                name="depthwise_conv1d",
            )

        conv_out = op.tensor_expr_op(
            _te_depthwise_conv,
            "depthwise_conv1d",
            [conv_state, x, self.conv1d_weight],
            attrs={"op_pattern": 8},
        )
        if self.conv1d_bias is not None:
            conv_out = conv_out + self.conv1d_bias
        return conv_out, new_conv_state


# ============================================================================
# Decoder layer + model
# ============================================================================


class Lfm3DecoderLayer(nn.Module):
    def __init__(self, config: Lfm3Config, layer_id: int, category_id: int):
        """category_id = index within this layer's category (conv layers vs attention layers)."""
        self.layer_type = config.layer_types[layer_id]
        self.is_attention = self.layer_type in ATTENTION_LAYER_TYPES
        if self.is_attention:
            self.self_attn = Lfm3Attention(config, self.layer_type)
        else:
            self.conv = Lfm3ShortConv(config, category_id)
        self.category_id = category_id
        self.feed_forward = Lfm3MLP(config)
        self.operator_norm = nn.RMSNorm(config.hidden_size, -1, config.norm_eps, bias=False)
        self.ffn_norm = nn.RMSNorm(config.hidden_size, -1, config.norm_eps, bias=False)
        self.use_sandwich_norm = config.use_sandwich_norm
        if config.use_sandwich_norm:
            self.post_operator_norm = nn.RMSNorm(config.hidden_size, -1, config.norm_eps, bias=False)
            self.post_ffn_norm = nn.RMSNorm(config.hidden_size, -1, config.norm_eps, bias=False)
        self.tensor_parallel_shards = config.tensor_parallel_shards

    def forward(self, hidden_states: Tensor, paged_kv_cache: PagedKVCache, state: RNNState, positions: Tensor):
        out = self.operator_norm(hidden_states)
        if self.is_attention:
            out = self.self_attn(out, paged_kv_cache, positions, self.category_id)
        else:
            out, state = self.conv(out, state)
        if self.use_sandwich_norm:
            out = self.post_operator_norm(out)
        hidden_states = self._apply_residual(out, residual=hidden_states)
        out = self.feed_forward(self.ffn_norm(hidden_states))
        if self.use_sandwich_norm:
            out = self.post_ffn_norm(out)
        hidden_states = self._apply_residual(out, residual=hidden_states)
        return hidden_states, state

    def _apply_residual(self, out, residual):
        if self.tensor_parallel_shards > 1:
            return op.ccl_allreduce(out, "sum") + residual
        return out + residual


class Lfm3Model(nn.Module):
    def __init__(self, config: Lfm3Config):
        self.embed_tokens = Lfm3Embedding(config.vocab_size, config.hidden_size)
        conv_idx = 0
        attn_idx = 0
        layers = []
        for i, ltype in enumerate(config.layer_types):
            if ltype in ATTENTION_LAYER_TYPES:
                layers.append(Lfm3DecoderLayer(config, i, category_id=attn_idx))
                attn_idx += 1
            else:
                layers.append(Lfm3DecoderLayer(config, i, category_id=conv_idx))
                conv_idx += 1
        self.layers = nn.ModuleList(layers)
        # HF: final norm is `embedding_norm`; remapped to `model.norm` in the loader.
        self.norm = nn.RMSNorm(config.hidden_size, -1, config.norm_eps, bias=False)

    def forward(self, inputs: Tensor, paged_kv_cache: PagedKVCache, state: RNNState):
        positions = paged_kv_cache.get_query_positions(inputs.shape[0] * inputs.shape[1])
        hidden_states = inputs
        for layer in self.layers:
            hidden_states, state = layer.forward(hidden_states, paged_kv_cache, state, positions)
        hidden_states = self.norm(hidden_states)
        return hidden_states, state


class Lfm3ForCausalLM(nn.Module):
    def __init__(self, config: Lfm3Config):
        self.config = config
        self.model = Lfm3Model(config)
        self.tie_word_embeddings = config.tie_word_embeddings
        if not config.tie_word_embeddings:
            self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.dtype = config.dtype
        self.hidden_size = config.hidden_size
        self.num_hidden_layers = config.num_hidden_layers
        self.num_attention_heads = config.num_attention_heads
        self.num_key_value_heads = config.num_key_value_heads
        self.head_dim = config.head_dim
        self.norm_eps = config.norm_eps
        self.vocab_size = config.vocab_size
        self.tensor_parallel_shards = config.tensor_parallel_shards
        self.num_attention_layers = config.num_attention_layers
        self.num_conv_layers = config.num_conv_layers
        self.conv_L_cache = config.conv_L_cache
        self.attention_kinds = [
            "mha_sliding" if t == "sliding_attention" else "mha"
            for t in config.layer_types
            if t in ATTENTION_LAYER_TYPES
        ]
        self.sliding_window = config.sliding_window

    def to(self, dtype: Optional[str] = None):
        super().to(dtype=dtype)
        if dtype is not None:
            self.dtype = dtype

    def embed(self, input_ids: Tensor):
        if self.tensor_parallel_shards > 1:
            input_ids = op.ccl_broadcast_from_worker0(input_ids)
        return self.model.embed_tokens(input_ids)

    def _forward(
        self,
        input_embed: Tensor,
        paged_kv_cache: PagedKVCache,
        state: RNNState,
        logit_positions: Optional[Tensor] = None,
    ):
        op_ext.configure()
        hidden_states, state = self.model.forward(input_embed, paged_kv_cache, state)
        if logit_positions is not None:
            hidden_states = op.take(hidden_states, logit_positions, axis=1)
        if self.tie_word_embeddings:
            logits = self.model.embed_tokens.lm_head_forward(hidden_states)
        else:
            logits = self.lm_head(hidden_states)
        if logits.dtype != "float32":
            logits = logits.astype("float32")
        return logits, paged_kv_cache, state

    def batch_prefill(
        self,
        input_embeds: Tensor,
        logit_positions: Tensor,
        paged_kv_cache: PagedKVCache,
        rnn_state: RNNState,
    ):
        if self.tensor_parallel_shards > 1:
            logit_positions = op.ccl_broadcast_from_worker0(logit_positions)
        return self._forward(input_embeds, paged_kv_cache, rnn_state, logit_positions)

    def batch_decode(self, input_embeds: Tensor, paged_kv_cache: PagedKVCache, rnn_state: RNNState):
        return self._forward(input_embeds, paged_kv_cache, rnn_state)

    def batch_verify(self, input_embeds: Tensor, paged_kv_cache: PagedKVCache, rnn_state: RNNState):
        return self._forward(input_embeds, paged_kv_cache, rnn_state)

    def create_rnn_state(self, max_batch_size: tirx.Var, max_history: tirx.Var) -> RNNState:
        # One state slot per conv layer: the ring buffer of the last (kernel - 1) `Bx` positions.
        conv_ks_m1 = self.conv_L_cache - 1
        init_values = [R.const(np.zeros((conv_ks_m1, self.hidden_size), self.dtype))]
        return RNNState.create(
            max_batch_size=max_batch_size,
            num_hidden_layers=self.num_conv_layers,
            max_history=max_history,
            init_values=init_values,
        )

    def create_paged_kv_cache(
        self,
        max_batch_size: tirx.Var,
        max_total_seq_len: tirx.Var,
        prefill_chunk_size: tirx.Var,
        page_size: tirx.Var,
        support_sliding_window: tirx.Var,
    ) -> PagedKVCache:
        return PagedKVCache.create_generic(
            # One entry per attention layer, in order: the sliding layers get the per-layer window.
            attn_kind=self.attention_kinds,
            max_batch_size=max_batch_size,
            max_total_seq_len=max_total_seq_len,
            prefill_chunk_size=prefill_chunk_size,
            page_size=page_size,
            support_sliding_window=support_sliding_window,
            num_hidden_layers=self.num_attention_layers,
            num_attention_heads=self.num_attention_heads // self.tensor_parallel_shards,
            num_key_value_heads=self.num_key_value_heads // self.tensor_parallel_shards,
            qk_head_dim=self.head_dim,
            v_head_dim=self.head_dim,
            rope_mode=RopeMode.NONE,
            rope_scale=1,
            rope_theta=int(self.config.rope_theta("full_attention")),
            dtype=self.dtype,
            layer_sliding_window_size=self.sliding_window,
        )

    def get_default_spec(self):
        mod_spec = {
            "embed": {
                "input_ids": nn.spec.Tensor(["seq_len"], "int32"),
                "$": {"param_mode": "packed", "effect_mode": "none"},
            },
            "batch_prefill": {
                "input_embeds": nn.spec.Tensor([1, "seq_len", self.hidden_size], self.dtype),
                "logit_positions": nn.spec.Tensor(["batch_size"], "int32"),
                "paged_kv_cache": nn.spec.Object(object_type=PagedKVCache),
                "rnn_state": nn.spec.Object(object_type=RNNState),
                "$": {"param_mode": "packed", "effect_mode": "none"},
            },
            "batch_decode": {
                "input_embeds": nn.spec.Tensor(["batch_size", 1, self.hidden_size], self.dtype),
                "paged_kv_cache": nn.spec.Object(object_type=PagedKVCache),
                "rnn_state": nn.spec.Object(object_type=RNNState),
                "$": {"param_mode": "packed", "effect_mode": "none"},
            },
            "batch_verify": {
                "input_embeds": nn.spec.Tensor([1, "seq_len", self.hidden_size], self.dtype),
                "paged_kv_cache": nn.spec.Object(object_type=PagedKVCache),
                "rnn_state": nn.spec.Object(object_type=RNNState),
                "$": {"param_mode": "packed", "effect_mode": "none"},
            },
            "create_paged_kv_cache": {
                "max_batch_size": int,
                "max_total_seq_len": int,
                "prefill_chunk_size": int,
                "page_size": int,
                "support_sliding_window": int,
                "$": {"param_mode": "none", "effect_mode": "none"},
            },
            "create_rnn_state": {
                "max_batch_size": int,
                "max_history": int,
                "$": {"param_mode": "none", "effect_mode": "none"},
            },
        }
        return nn.spec.ModuleSpec.from_raw(mod_spec, self)
