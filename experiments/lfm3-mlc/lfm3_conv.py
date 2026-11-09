"""LFM3 conversation template: ChatML with a `<|startoftext|>` BOS prefix (124894) and `<|im_end|>`
(124900) as the turn separator + stop. No default system prompt (LFM3's chat template only writes a
system block when one is given). Thinking is the model's default: the reply opens with <think>.
Tools, tool calls and tool results are not rendered here; Squiggle sends those as raw completions."""

from mlc_llm.protocol.conversation_protocol import Conversation, MessagePlaceholders

from .registry import ConvTemplateRegistry

ConvTemplateRegistry.register_conv_template(
    Conversation(
        name="lfm3",
        system_template=f"<|im_start|>system\n{MessagePlaceholders.SYSTEM.value}<|im_end|>\n",
        system_message="",
        roles={"user": "<|im_start|>user", "assistant": "<|im_start|>assistant"},
        seps=["<|im_end|>\n"],
        role_content_sep="\n",
        role_empty_sep="\n",
        stop_str=["<|im_end|>", "<|endoftext|>"],
        stop_token_ids=[124900, 124895],
        system_prefix_token_ids=[124894],  # <|startoftext|>
    )
)
