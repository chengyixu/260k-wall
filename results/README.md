# Result artifacts

## `raw/`

Original benchmark outputs copied from the experiment workspace:

- JSON/JSONL request measurements;
- context-sentinel proofs;
- planner/executor records;
- tool-call output;
- selected server logs needed to validate prompt/decode timing.

The only transformations applied to copied logs were replacing the local macOS username in absolute paths with `<user>`. Timing lines, token counts, generated outputs, and hashes were not altered.

## `processed/`

- `summary.json`: compact set of values used by the figures and headline tables;
- `environment.json`: hardware, OS, runtime commits, configuration, and binary hashes;
- `splash_model_manifest.json`: complete packed-package artifact hashes and upstream revisions;
- `bonsai_manifest.json`: Bonsai model/runtime provenance with the local username redacted;
- `generated_lru_*.py`: model-generated code retained as executable quality gates.

## Interpretation warning

Records contain several throughput notions:

- server decode TPS;
- client post-TTFT streaming TPS;
- final-answer tokens divided by total planner/executor wall time;
- aggregate planner-plus-executor generated TPS.

Read [`../RESULTS.md`](../RESULTS.md) before comparing numbers. The project intentionally does not collapse all of these metrics into one headline.

`../SHA256SUMS` covers all published artifact content except itself and the Hub-managed `.gitattributes` file.
