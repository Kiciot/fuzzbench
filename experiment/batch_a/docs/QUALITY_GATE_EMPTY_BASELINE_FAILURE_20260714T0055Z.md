# Batch A empty-corpus baseline infrastructure failure

## Preserved failed attempt

- Quality root: `/data/adarare_exp/batch_a/results/quality_gate_20260713t232914z`
- Failed stage: `core-rest`
- Experiment: `baqcorerest-0714005340`
- FuzzBench commit: `5641f76d3d3c4058cbd4ff2e4d00cdb82109b39e`
- AFL++ commit: `8224da1dce693d0a7de8d21cd9108c4e0e3a5b54`
- The partial result directory is retained and was not overwritten or deleted.

The stage was stopped after cycle zero had deterministically emitted 20
`Coverage run failed` errors: ten for `proj4_proj_crs_to_crs_fuzzer` and ten
for `openh264_decoder_fuzzer`.  Each error reported `MERGE-OUTER: 0 files`.
Because the strict quality auditor rejects every coverage-run failure, this
attempt could not pass and was not allowed to continue to the formal gate.

## Root cause

Both benchmarks have an empty packaged seed corpus.  `TrialRunner` archived
the time-zero corpus before starting the fuzzer process.  The AFL integration
then materialized its long-standing deterministic fallback seed
`default_seed` with contents `hi` immediately before launching `afl-fuzz`.
Consequently, the archived baseline was empty even though the actual fuzzing
input corpus was not.  This was a measurement-ordering error, not a target,
benchmark-revision, or AdaRare-policy failure.

## Semantic-preserving correction

The AdaRare wrapper now exposes the existing idempotent seed preparation as a
runner hook.  `TrialRunner` invokes that hook before copying and synchronizing
the time-zero corpus.  The fuzzer still invokes the same helper during normal
startup, where it is a no-op because the seed already exists.  No seed content
was added or changed relative to the corpus that AFL already consumed.

The correction does not change benchmark revisions, target binaries, coverage
binaries, CmpLog binaries, sanitizer, compiler flags, AdaRare policy, variant
environment, trial count, time budget, or target list.

## Validation before rebuild

- The ten formal variant `fuzzer.py` files are byte-identical.
- Related unit tests: 52 passed, 1 skipped.
- The hook is tested on empty and non-empty corpora and is idempotent.
- Running the existing coverage pipeline on the same fallback seed succeeded
  for both affected targets: proj4 reported 57 covered branches and openh264
  reported 172 covered branches.

These diagnostics did not start a FuzzBench runner.  The repaired commit still
must pass a fresh 60-build matrix, provenance/hash equivalence, and the entire
runtime quality gate.  No previous PASS is carried across the commit change.

One sqlite Full trial had a recorded start but had not produced a time-zero
archive when the already-invalid stage was stopped.  Because the run was
terminated early, no independent conclusion is drawn from that partial trial.
