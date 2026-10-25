#!/usr/bin/env python3
"""Streaming decode bench against a local OpenAI-compatible llama-server."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def stream_chat(base: str, model: str, prompt: str, max_tokens: int, temperature: float = 0.0, api_key: str = ""):
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False},
        }
    ).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    t0 = time.perf_counter()
    ttft = None
    chunks = []
    usage = {}
    timings = {}
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            obj = json.loads(payload)
            if obj.get("usage"):
                usage = obj["usage"]
            if obj.get("timings"):
                timings = obj["timings"]
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content") or delta.get("reasoning_content") or ""
            if piece:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(piece)
    total = time.perf_counter() - t0
    text = "".join(chunks)
    return {
        "ttft_s": ttft,
        "total_s": total,
        "chars": len(text),
        "text_preview": text[:240].replace("\n", " "),
        "usage": usage,
        "timings": timings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18791")
    ap.add_argument("--model", default="")
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--prompt", default="Write a Python function that returns the nth Fibonacci number. Only code.")
    ap.add_argument("--out", default="")
    ap.add_argument("--api-key", default="")
    args = ap.parse_args()

    if not args.model:
        req = urllib.request.Request(args.base.rstrip("/") + "/v1/models")
        if args.api_key:
            req.add_header("Authorization", f"Bearer {args.api_key}")
        with urllib.request.urlopen(req, timeout=10) as r:
            models = json.load(r).get("data") or []
            args.model = models[0]["id"] if models else "local"

    rows = []
    for i in range(args.runs):
        rec = stream_chat(args.base, args.model, args.prompt, args.max_tokens, api_key=args.api_key)
        usage = rec.get("usage") or {}
        timings = rec.get("timings") or {}
        out_tok = usage.get("completion_tokens") or timings.get("predicted_n") or usage.get("output_tokens")
        if not out_tok:
            out_tok = max(1, rec["chars"] // 4)
        decode_s = rec["total_s"] - (rec["ttft_s"] or 0)
        wall_tps = (out_tok / decode_s) if decode_s > 0.01 else None
        tps = timings.get("predicted_per_second") or wall_tps
        row = {
            "label": args.label,
            "run": i,
            "model": args.model,
            "prompt_tokens": usage.get("prompt_tokens") or timings.get("prompt_n"),
            "completion_tokens": out_tok,
            "ttft_s": rec["ttft_s"],
            "total_s": rec["total_s"],
            "decode_s": decode_s,
            "decode_tps": tps,
            "wall_decode_tps": wall_tps,
            "prompt_per_second": timings.get("prompt_per_second"),
            "draft_n": timings.get("draft_n") or timings.get("predicted_draft_n"),
            "preview": rec["text_preview"],
            "timings": timings,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)

    tps_vals = [r["decode_tps"] for r in rows if r["decode_tps"]]
    tps_vals.sort()
    summary = {
        "label": args.label,
        "summary": True,
        "n": len(rows),
        "median_decode_tps": tps_vals[len(tps_vals) // 2] if tps_vals else None,
        "min_decode_tps": tps_vals[0] if tps_vals else None,
        "max_decode_tps": tps_vals[-1] if tps_vals else None,
        "median_ttft_s": sorted(r["ttft_s"] or 0 for r in rows)[len(rows) // 2],
    }
    print(json.dumps(summary), flush=True)
    if args.out:
        with open(args.out, "a") as f:
            for r in rows + [summary]:
                f.write(json.dumps(r) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
