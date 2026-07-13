#!/usr/bin/env python3
"""Fail-closed build provenance and cross-variant equivalence gate."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

FUZZERS = [
    "adarare_full",
    "adarare_linucb_no_a6",
    "adarare_constant_context_no_a6",
    "adarare_random_profile",
    "adarare_round_robin_profile",
    "adarare_static_a1",
    "adarare_static_a2",
    "adarare_static_a3",
    "adarare_static_a4",
    "adarare_static_a5",
]
BENCHMARKS = [
    "curl_curl_fuzzer_http",
    "lcms_cms_transform_fuzzer",
    "proj4_proj_crs_to_crs_fuzzer",
    "sqlite3_ossfuzz",
    "openh264_decoder_fuzzer",
    "freetype2_ftfuzzer",
]
EXPECTED_ENV = {
    "adarare_full": {
        "AFL_ADARARE_POLICY": "linucb",
        "AFL_ADARARE_ENABLE_A6": "1",
        "AFL_ADARARE_CONTEXT_MODE": "dynamic",
    },
    "adarare_linucb_no_a6": {
        "AFL_ADARARE_POLICY": "linucb",
        "AFL_ADARARE_ENABLE_A6": "0",
        "AFL_ADARARE_CONTEXT_MODE": "dynamic",
    },
    "adarare_constant_context_no_a6": {
        "AFL_ADARARE_POLICY": "linucb",
        "AFL_ADARARE_ENABLE_A6": "0",
        "AFL_ADARARE_CONTEXT_MODE": "constant",
    },
    "adarare_random_profile": {
        "AFL_ADARARE_POLICY": "random_profile",
        "AFL_ADARARE_ENABLE_A6": "0",
        "AFL_ADARARE_CONTEXT_MODE": "dynamic",
    },
    "adarare_round_robin_profile": {
        "AFL_ADARARE_POLICY": "round_robin_profile",
        "AFL_ADARARE_ENABLE_A6": "0",
        "AFL_ADARARE_CONTEXT_MODE": "dynamic",
    },
    **{
        f"adarare_static_a{i}": {
            "AFL_ADARARE_POLICY": "static_profile",
            "AFL_ADARARE_ENABLE_A6": "0",
            "AFL_ADARARE_CONTEXT_MODE": "dynamic",
            "AFL_ADARARE_STATIC_ARM": str(i),
        }
        for i in range(1, 6)
    },
}

EQUIVALENT_FIELDS = [
    "benchmark_revision",
    "benchmark_yaml_sha256",
    "benchmark_dockerfile_sha256",
    "target_binary_sha256",
    "coverage_binary_sha256",
    "cmplog_binary_sha256",
    "initial_corpus_manifest_sha256",
    "seed_file_count",
    "dictionary_manifest_sha256",
    "dictionary_file_count",
]
GLOBAL_IDENTICAL_FIELDS = [
    "fuzzbench_commit",
    "aflplusplus_commit",
    "builder_dockerfile_sha256",
    "fuzzer_py_sha256",
    "normalized_runner_sha256",
]


def parse_env(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in filter(None, value.split(";")):
        key, sep, val = item.partition("=")
        if not sep:
            raise ValueError(f"malformed variant env item: {item!r}")
        result[key] = val
    return result


def resolve_default() -> Path:
    marker = Path("/data/adarare_exp/batch_a/manifests/latest_build_provenance.txt")
    if not marker.is_file():
        raise FileNotFoundError(f"missing {marker}")
    return Path(marker.read_text(encoding="utf-8").strip()) / "build_provenance.tsv"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("provenance", nargs="?", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    provenance = args.provenance or resolve_default()
    out = args.output_dir or provenance.parent
    out.mkdir(parents=True, exist_ok=True)

    with provenance.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    audit_rows: list[tuple[str, str, str, int, str]] = []
    failures: list[str] = []

    def record(scope: str, field: str, values: list[str], expected_unique: int = 1) -> None:
        distinct = sorted(set(values))
        ok = len(distinct) == expected_unique and all(value != "" for value in distinct)
        status = "PASS" if ok else "FAIL"
        audit_rows.append((scope, field, status, len(distinct), " | ".join(distinct)))
        if not ok:
            failures.append(f"{scope}: {field} has {len(distinct)} distinct values")

    if len(rows) != 60:
        failures.append(f"expected 60 provenance rows, got {len(rows)}")
    pairs = Counter((row.get("benchmark", ""), row.get("fuzzer", "")) for row in rows)
    expected_pairs = {(benchmark, fuzzer) for benchmark in BENCHMARKS for fuzzer in FUZZERS}
    if set(pairs) != expected_pairs or any(count != 1 for count in pairs.values()):
        missing = sorted(expected_pairs - set(pairs))
        extra = sorted(set(pairs) - expected_pairs)
        failures.append(f"pair matrix mismatch missing={missing} extra={extra} duplicates={[(p,c) for p,c in pairs.items() if c != 1]}")

    by_benchmark: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_benchmark[row.get("benchmark", "")].append(row)
    for benchmark in BENCHMARKS:
        group = by_benchmark.get(benchmark, [])
        if len(group) != 10:
            failures.append(f"{benchmark}: expected 10 rows, got {len(group)}")
        for field in EQUIVALENT_FIELDS:
            record(benchmark, field, [row.get(field, "") for row in group])

    for field in GLOBAL_IDENTICAL_FIELDS:
        record("GLOBAL", field, [row.get(field, "") for row in rows])

    for row in rows:
        fuzzer = row.get("fuzzer", "")
        try:
            actual = parse_env(row.get("variant_env", ""))
        except ValueError as error:
            failures.append(f"{row.get('benchmark')}/{fuzzer}: {error}")
            continue
        expected = EXPECTED_ENV.get(fuzzer)
        if expected is None or actual != expected:
            failures.append(
                f"{row.get('benchmark')}/{fuzzer}: variant env mismatch actual={actual} expected={expected}"
            )

    tsv_path = out / "hash_equivalence.tsv"
    with tsv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["scope", "field", "status", "distinct_count", "values"])
        writer.writerows(audit_rows)

    result = {
        "status": "PASS" if not failures else "FAIL",
        "provenance": str(provenance),
        "records": len(rows),
        "benchmarks": BENCHMARKS,
        "fuzzers": FUZZERS,
        "failures": failures,
    }
    json_path = out / "hash_equivalence.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
