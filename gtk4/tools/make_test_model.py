#!/usr/bin/env python3
"""Write a tiny GGUF model with random weights (about 17 MB) for testing the
AI engine without downloading a real model: tests/test_engine.py uses it.

Its answers are noise, but the output grammar still forces them into the
JSON shape the app parses, so loading, the reusable prompt prefix,
grammar-constrained sampling, cancellation and the review cache can all be
exercised. Uses gguf-py and the bundled test vocabulary from the llama.cpp
checkout in vendor/, and numpy.

    python3 tools/make_test_model.py                  # → build/test-model.gguf
    python3 tools/make_test_model.py LLAMA_SRC OUT.gguf
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "vendor" / "llama.cpp"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "test-model.gguf"
sys.path.insert(0, str(src / "gguf-py"))

import numpy as np  # noqa: E402
import gguf  # noqa: E402

vocab = gguf.GGUFReader(str(src / "models" / "ggml-vocab-llama-spm.gguf"))
out.parent.mkdir(parents=True, exist_ok=True)
w = gguf.GGUFWriter(str(out), "llama")
n_embd, n_head, n_layer, n_ff, n_ctx = 64, 4, 2, 128, 4096
w.add_name("tiny-test")
w.add_context_length(n_ctx)
w.add_embedding_length(n_embd)
w.add_block_count(n_layer)
w.add_feed_forward_length(n_ff)
w.add_head_count(n_head)
w.add_head_count_kv(n_head)
w.add_layer_norm_rms_eps(1e-5)
w.add_rope_dimension_count(n_embd // n_head)
w.add_chat_template("{% for m in messages %}<|im_start|>{{ m.role }}\n{{ m.content }}<|im_end|>{% endfor %}")

# The tokenizer, copied from the vocabulary-only test file.
setters = {gguf.GGUFValueType.UINT32: w.add_uint32, gguf.GGUFValueType.INT32: w.add_int32,
           gguf.GGUFValueType.BOOL: w.add_bool, gguf.GGUFValueType.FLOAT32: w.add_float32}
for f in vocab.fields.values():
    if not f.name.startswith("tokenizer."):
        continue
    kind = f.types[0]
    if kind == gguf.GGUFValueType.ARRAY:
        values = [f.parts[i] for i in f.data]
        if f.types[1] == gguf.GGUFValueType.STRING:
            values = [bytes(v).decode("utf-8", "replace") for v in values]
        else:
            values = [v[0].item() for v in values]
        w.add_array(f.name, values)
    elif kind == gguf.GGUFValueType.STRING:
        w.add_string(f.name, bytes(f.parts[f.data[0]]).decode())
    else:
        setters[kind](f.name, f.parts[f.data[0]][0].item())

n_vocab = len(vocab.fields["tokenizer.ggml.tokens"].data)
rng = np.random.default_rng(1)


def tensor(name: str, *shape: int) -> None:
    w.add_tensor(name, (rng.standard_normal(shape) * 0.02).astype(np.float32))


tensor("token_embd.weight", n_vocab, n_embd)
w.add_tensor("output_norm.weight", np.ones(n_embd, dtype=np.float32))
tensor("output.weight", n_vocab, n_embd)
for i in range(n_layer):
    w.add_tensor(f"blk.{i}.attn_norm.weight", np.ones(n_embd, dtype=np.float32))
    w.add_tensor(f"blk.{i}.ffn_norm.weight", np.ones(n_embd, dtype=np.float32))
    for n in ("attn_q", "attn_k", "attn_v", "attn_output"):
        tensor(f"blk.{i}.{n}.weight", n_embd, n_embd)
    tensor(f"blk.{i}.ffn_gate.weight", n_ff, n_embd)
    tensor(f"blk.{i}.ffn_up.weight", n_ff, n_embd)
    tensor(f"blk.{i}.ffn_down.weight", n_embd, n_ff)
w.write_header_to_file()
w.write_kv_data_to_file()
w.write_tensors_to_file()
w.close()
print(f"Wrote {out}")
