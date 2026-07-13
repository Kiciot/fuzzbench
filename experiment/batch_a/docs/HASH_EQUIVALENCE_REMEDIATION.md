# Batch A Hash Equivalence Remediation

## Initial gate result

The first strict hash-equivalence audit failed before any fuzzing runner was
started. The preserved audit reported ten distinct raw target and CmpLog hashes
for curl and ten distinct generated `afl++.dict` manifests for five benchmarks.

## Root cause evidence

Read-only comparison of the independently rebuilt curl artifacts showed:

- identical `.text`, `.rodata`, `.data`, and `.debug_info` section hashes;
- different `.debug_line` hashes;
- identical target and CmpLog hashes after removing debug sections;
- identical `afl++.dict` hashes after sorting, including after sorting uniquely.

The mismatch therefore came from non-semantic debug metadata and generated
dictionary ordering in independently rebuilt artifacts. It was not caused by a
different AFL++ commit, benchmark revision, instrumentation policy, corpus, or
variant runtime environment.

## Remediation boundary

For each benchmark, the `adarare_full` builder image is the canonical build
artifact because every Batch A builder Dockerfile and `fuzzer.py` is byte-for-byte
identical and pins the same AFL++ commit. The canonical builder image is retagged
for the other nine variants, and only each variant's final runner image is
rebuilt from its already-built runtime-specific intermediate image.

This preserves the variant runtime environment while making the target,
coverage, CmpLog, seed corpus, and dictionary artifacts byte-identical. It does
not change the benchmark revision, source, compiler flags, sanitizer, corpus,
dictionary content, policy, or runtime environment.

The failed provenance and hash audit are retained alongside the build result.
