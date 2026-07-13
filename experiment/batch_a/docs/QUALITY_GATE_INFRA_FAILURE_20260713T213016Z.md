# Batch A curl quality-gate infrastructure failure

- Attempt root: `/data/adarare_exp/batch_a/results/quality_gate_20260713t213016z`
- Experiment: `baqcurl-0713213016`
- FuzzBench commit: `93965fd72a3c0d447d7854f878339078c532b6f1`
- AFL++ commit: `8224da1dce693d0a7de8d21cd9108c4e0e3a5b54`
- Classification: **FuzzBench terminal archive collection failure**
- Curl target/fallback decision: **not made from this invalid attempt**

The ten runners exited cleanly and were not preempted.  Deterministic time-zero
coverage was 6960 for all variants, and coverage grew normally through the
2700-second snapshot.  At the 3600-second boundary, the runner wrote the
periodic terminal archive and immediately performed a final sync using the same
`corpus-archive-0004.tar.gz` name.  The second incremental sync replaced each
complete terminal archive with a 69-byte archive containing zero files.

The measurer consequently emitted ten `Coverage run failed` errors with
`MERGE-OUTER: 0 files`.  The recorded 3600-second coverage merely repeated the
2700-second accumulated value for all ten variants and is invalid as terminal
quality evidence.  This attempt remains preserved and must not be used for
performance comparison or for the curl/freetype2 target decision.

The remediation gives the final sync a distinct cycle number, reconstructs
telemetry across incremental archives, fails closed on an empty in-budget
terminal archive or any coverage-run failure, and adds regression tests.  A new
complete build/provenance gate and one-hour curl quality gate are required.
