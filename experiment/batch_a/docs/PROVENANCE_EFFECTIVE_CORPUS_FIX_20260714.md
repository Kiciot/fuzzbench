# Batch A Effective Corpus Provenance Fix (2026-07-14)

## Scope

This change fixes the Batch A build-provenance gate. It does not change a
benchmark revision, target binary, runtime variant environment, initial corpus,
or fuzzing policy.

## Invalidated provenance attempt

The provenance output under
`/data/adarare_exp/batch_a/results/build_matrix_20260714T010526Z/provenance`
was collected by the previous tool and is explicitly marked
`INVALID_NOT_A_GATE.txt`. It must not be used to satisfy the provenance or hash
equivalence gate.

The previous collector hashed the static `/out/seeds` directory without running
the runner's corpus setup. That omitted both the normal seed-corpus archive
unpacking/cleaning path and the deterministic AdaRare fallback seed used when a
benchmark archive is absent or empty.

## Corrected provenance path

For every benchmark-variant runner image, the collector now creates a temporary
container and invokes the same `TrialRunner.initialize_directories()` and
`TrialRunner.set_up_corpus_directories()` sequence used before fuzzing. It then
hashes the resulting `/out/seeds` files in sorted relative-path order.

The collector additionally records:

- the source seed-corpus archive hash, or an explicit no-archive marker;
- the runtime runner source hash;
- the runtime fuzzer integration source hash;
- the FuzzBench commit recorded by the clean build and verifies that it equals
  the clean current checkout.

An empty effective runtime seed corpus is a hard provenance failure.

## Smoke evidence

The corrected extraction path was exercised against the current runner images:

- curl materialized 41 effective seed files;
- proj4 materialized one `default_seed` containing the existing deterministic
  `hi` fallback (SHA256
  `8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4`);
- openh264 materialized the same deterministic fallback seed.

## Gate consequence

Because this correction changes the retained FuzzBench workflow commit, the
60-build matrix, canonicalization, provenance collection, and hash equivalence
gate must all be rerun from a clean build result at the new commit. No quality
runner or formal experiment may start from the invalidated provenance attempt.
