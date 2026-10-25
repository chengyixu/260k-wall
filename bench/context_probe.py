#!/usr/bin/env python3
"""Prove a real >=256k request against a local OpenAI-compatible server."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_SENTINEL = "BONSAI2-262K-NEEDLE-91D7"


def build_prompt(tokenizer: Any, minimum_content_tokens: int, sentinel: str) -> tuple[str, int]:
    unit = " cache"
    unit_ids = tokenizer.encode(unit, add_special_tokens=False)
    if not unit_ids:
        raise RuntimeError("Tokenizer produced no filler tokens")
    prefix = "Archive data follows. Preserve the final audit sentinel.\n"
    suffix = f"\n\nThe audit sentinel is {sentinel}. Reply with the audit sentinel only."
    fixed = len(tokenizer.encode(prefix + suffix, add_special_tokens=False))
    filler_count = max(0, minimum_content_tokens - fixed)
    filler_ids = (unit_ids * ((filler_count + len(unit_ids) - 1) // len(unit_ids)))[:filler_count]
    prompt = prefix + tokenizer.decode(filler_ids, skip_special_tokens=False) + suffix
    count = len(tokenizer.encode(prompt, add_special_tokens=False))
    if count < minimum_content_tokens:
        raise RuntimeError(f"Built only {count} tokens; expected {minimum_content_tokens}")
    return prompt, count


def parse_result(
    raw: dict[str, Any], model: str, requested_tokens: int, sentinel: str, elapsed_s: float
) -> dict[str, Any]:
    message = (raw.get("choices") or [{}])[0].get("message") or {}
    answer = message.get("content") or ""
    usage = raw.get("usage") or {}
    timings = raw.get("timings") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or timings.get("prompt_n") or 0)
    return {
        "model": model,
        "requested_content_tokens": requested_tokens,
        "server_prompt_tokens": prompt_tokens,
        "completion_tokens": usage.get("completion_tokens") or timings.get("predicted_n"),
        "latency_s": round(elapsed_s, 3),
        "decode_tps": timings.get("predicted_per_second"),
        "prompt_tps": timings.get("prompt_per_second"),
        "answer": answer.strip(),
        "sentinel_found": sentinel in answer,
        "context_256k_proven": prompt_tokens >= 256_000 and sentinel in answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:7870/v1")
    parser.add_argument("--model", default="Ternary-Bonsai-2-27B-PQ2_0")
    parser.add_argument("--api-key-file", type=Path)
    parser.add_argument("--content-tokens", type=int, default=260_000)
    parser.add_argument("--sentinel", default=DEFAULT_SENTINEL)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_dir, local_files_only=True, trust_remote_code=False
    )
    prompt, built_tokens = build_prompt(tokenizer, args.content_tokens, args.sentinel)
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
        "temperature": 0,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
    }
    headers = {"Content-Type": "application/json"}
    if args.api_key_file:
        headers["Authorization"] = f"Bearer {args.api_key_file.read_text().strip()}"
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        raw = json.loads(response.read())
    elapsed = time.perf_counter() - started
    record = parse_result(raw, args.model, args.content_tokens, args.sentinel, elapsed)
    record["client_built_tokens"] = built_tokens
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    if not record["context_256k_proven"]:
        raise SystemExit("256k context verification failed")


if __name__ == "__main__":
    main()
