#!/usr/bin/env python3
import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
data = json.loads((ROOT / "results/processed/summary.json").read_text())

# Short/candidate throughput.
labels = [
    "Q6 AR", "Q6 MTP", "Q6 DFlash2", "MLX AR", "MLX DFlash2",
    "oMLX DFlash2", "DSpark DFlash", "Bonsai 2", "Splash medium",
]
values = [
    data["short_and_candidate_results"]["qwen27_q6_llamacpp_ar_tps"],
    data["short_and_candidate_results"]["qwen27_q6_llamacpp_mtp_tps"],
    data["short_and_candidate_results"]["qwen27_q6_llamacpp_dflash2_tps"],
    data["short_and_candidate_results"]["mlx_qwen27_4bit_ar_tps"],
    data["short_and_candidate_results"]["mlx_qwen27_4bit_dflash2_tps"],
    data["short_and_candidate_results"]["omlx_dflash2_262k_slot_tps"],
    data["short_and_candidate_results"]["mlx_dspark_dflash_kv4_tps"],
    data["short_and_candidate_results"]["bonsai_short_code_tps"],
    data["short_and_candidate_results"]["splash_short_medium_tps"],
]
colors = ["#888888"] * 3 + ["#4C78A8", "#4C78A8", "#F58518", "#F58518", "#54A24B", "#E45756"]
fig, ax = plt.subplots(figsize=(9, 4.8))
bars = ax.bar(range(len(labels)), values, color=colors)
ax.axhline(20, color="black", linestyle="--", linewidth=1, label="20 tok/s gate")
ax.set_ylabel("Decode throughput (tok/s)")
ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
ax.set_title("Candidate throughput on Apple M4 Max 64 GB")
for bar, value in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, value + .5, f"{value:.1f}", ha="center", fontsize=8)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(OUT / "candidate_throughput.pdf")
fig.savefig(OUT / "candidate_throughput.png", dpi=180)
plt.close(fig)

# Near-limit comparison.
labels = ["Bonsai F16", "Bonsai q4 KV", "Splash medium\ndirect", "Splash low\ndirect", "Splash none\ndirect", "Champion executor"]
values = [
    data["context_proofs"]["bonsai_f16"]["decode_tps"],
    data["context_proofs"]["bonsai_q4"]["decode_tps"],
    data["full_context_reasoning_results"]["splash_medium_realistic_coding_tps"],
    data["full_context_reasoning_results"]["splash_low_realistic_coding_median_tps"],
    data["full_context_reasoning_results"]["splash_none_realistic_coding_median_tps"],
    data["champion_results"]["three_run_executor_median_tps"],
]
fig, ax = plt.subplots(figsize=(8.5, 4.8))
bars = ax.bar(range(len(labels)), values, color=["#54A24B", "#54A24B", "#E45756", "#E45756", "#E45756", "#B279A2"])
ax.axhline(20, color="black", linestyle="--", linewidth=1, label="20 tok/s gate")
ax.set_ylabel("Decode throughput (tok/s)")
ax.set_xticks(range(len(labels)), labels, rotation=20, ha="right")
ax.set_title("Realistic near-limit (260k) decoding")
for bar, value in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, value + .45, f"{value:.1f}", ha="center", fontsize=9)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(OUT / "near_limit_throughput.pdf")
fig.savefig(OUT / "near_limit_throughput.png", dpi=180)
plt.close(fig)

# Architecture diagram.
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.axis("off")
boxes = [
    (0.03, 0.40, 0.16, 0.25, "Agent client\nPi / OpenAI"),
    (0.24, 0.40, 0.19, 0.25, "Champion proxy\npolicy + routing"),
    (0.49, 0.62, 0.20, 0.25, "Compact planner\nmedium · 128 tok"),
    (0.49, 0.18, 0.20, 0.25, "260k executor\nreasoning off"),
    (0.75, 0.40, 0.22, 0.25, "Splash PR #3\nQwen3.8 + DFlash2\nQ8 KV + SSD tier"),
]
for x, y, w, h, text in boxes:
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor="#F3F4F6", edgecolor="#333333", linewidth=1.3))
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=10)
def arrow(x1,y1,x2,y2):
    ax.annotate("", xy=(x2,y2), xytext=(x1,y1), arrowprops=dict(arrowstyle="->", lw=1.5, color="#333333"))
arrow(.19,.525,.24,.525); arrow(.43,.55,.49,.745); arrow(.69,.745,.75,.56); arrow(.43,.47,.49,.305); arrow(.69,.305,.75,.49)
ax.text(.57,.49,"plan",ha="center",fontsize=9,color="#555555")
ax.set_title("Compact-plan / full-context-execute serving path", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "champion_architecture.pdf")
fig.savefig(OUT / "champion_architecture.png", dpi=180)
plt.close(fig)
