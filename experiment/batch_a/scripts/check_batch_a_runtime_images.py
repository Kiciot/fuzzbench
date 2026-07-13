#!/usr/bin/env python3
"""Fail closed unless local Batch A runner tags match build provenance."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--benchmarks", required=True, nargs="+")
    args = parser.parse_args()

    with args.provenance.open(newline="", encoding="utf-8") as handle:
        provenance = list(csv.DictReader(handle, delimiter="\t"))
    wanted = set(args.benchmarks)
    rows = [row for row in provenance if row["benchmark"] in wanted]
    output = []
    for row in rows:
        tag = (f"gcr.io/fuzzbench/runners/{row['fuzzer']}/"
               f"{row['benchmark']}:latest")
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
            text=True, capture_output=True, check=False)
        actual = result.stdout.strip() if result.returncode == 0 else ""
        expected = row["runner_image_id"]
        output.append({
            "benchmark": row["benchmark"], "fuzzer": row["fuzzer"],
            "runner_tag": tag, "expected_image_id": expected,
            "actual_image_id": actual,
            "status": "PASS" if actual == expected and actual else "FAIL",
        })

    expected_count = len(wanted) * 10
    complete = (len(rows) == expected_count and
                {row["benchmark"] for row in rows} == wanted and
                all(row["status"] == "PASS" for row in output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]) if output else ["status"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    if not complete:
        print(f"runtime image gate FAIL: expected={expected_count} rows={len(rows)}")
        return 1
    print(f"runtime image gate PASS: {len(rows)}/{expected_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
