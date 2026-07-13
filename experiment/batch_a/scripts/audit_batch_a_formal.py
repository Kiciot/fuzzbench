#!/usr/bin/env python3
"""Complete, fail-closed audit and checksum freeze for Batch A formal data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from typing import Any

from audit_batch_a_quality_gate import (
    EXPECTED, FUZZERS, arm_rows, latest_archive, pick, read_members,
)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_config(data: bytes | None) -> dict[str, Any]:
    if not data:
        return {}
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    batch = Path("/data/adarare_exp/batch_a")
    formal_root = args.root
    if formal_root is None:
        formal_root = Path((batch / "manifests/latest_formal_root.txt").read_text().strip())
    formal_root = formal_root.resolve()
    freeze_json = batch / "freeze/batch_a_pre_run_freeze.json"
    frozen = json.loads(freeze_json.read_text(encoding="utf-8"))
    targets = frozen["targets"]
    expected_pairs = {(b, f) for b in targets for f in FUZZERS}

    db_path = formal_root / "experiment-data/local.db"
    if not db_path.is_file():
        raise SystemExit(f"missing formal database: {db_path}")
    exp_dirs = [p for p in (formal_root / "experiment-data").iterdir()
                if p.is_dir() and (p / "experiment-folders").is_dir()]
    if len(exp_dirs) != 1:
        raise SystemExit(f"cannot uniquely locate formal experiment folder: {exp_dirs}")
    exp_root = exp_dirs[0]

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    trials = list(connection.execute(
        "select id,fuzzer,benchmark,time_started,time_ended,preempted,trial_group_num from trial order by benchmark,fuzzer,trial_group_num"
    ))
    failures: list[str] = []
    completeness: list[dict[str, Any]] = []
    terminal_audit: list[dict[str, Any]] = []
    telemetry_audit: list[dict[str, Any]] = []
    policy_audit: list[dict[str, Any]] = []
    cell_counts: list[dict[str, Any]] = []
    hash_audit: list[dict[str, Any]] = []

    actual_pairs = {(r["benchmark"], r["fuzzer"]) for r in trials}
    if len(trials) != 500 or actual_pairs != expected_pairs:
        failures.append(f"campaign matrix mismatch trials={len(trials)} cells={len(actual_pairs)}")

    initial_by_cell: dict[tuple[str, str], list[int]] = {}
    initial_by_benchmark: dict[str, list[int]] = {b: [] for b in targets}
    for benchmark, fuzzer in sorted(expected_pairs):
        cell = [r for r in trials if r["benchmark"] == benchmark and r["fuzzer"] == fuzzer]
        trial_nums = sorted(r["trial_group_num"] for r in cell)
        cell_ok = len(cell) == 10 and trial_nums == list(range(10))
        if not cell_ok:
            failures.append(f"{benchmark}/{fuzzer}: expected trial_group_num 0..9, got {trial_nums}")
        cell_counts.append({
            "benchmark": benchmark, "fuzzer": fuzzer, "count": len(cell),
            "trial_group_nums": ";".join(map(str, trial_nums)),
            "status": "PASS" if cell_ok else "FAIL",
        })

    for trial in trials:
        trial_id = trial["id"]
        benchmark, fuzzer = trial["benchmark"], trial["fuzzer"]
        snaps = list(connection.execute(
            "select time,edges_covered from snapshot where trial_id=? order by time", (trial_id,)
        ))
        times = [int(r["time"]) for r in snaps]
        cov = [int(r["edges_covered"]) for r in snaps]
        initial = cov[0] if times and times[0] == 0 else -1
        terminal_time = times[-1] if times else -1
        terminal = cov[-1] if cov else -1
        monotonic = all(a <= b for a, b in zip(cov, cov[1:]))
        expected_through_terminal = set(range(0, terminal_time + 1, 900)) if terminal_time >= 0 else set()
        missing = sorted(expected_through_terminal - set(times))
        clean_end = trial["time_started"] is not None and trial["time_ended"] is not None and not trial["preempted"]
        terminal_ok = terminal_time in (85500, 86400)
        row_fail = []
        if not clean_end: row_fail.append("runner_not_cleanly_completed")
        if initial < 0: row_fail.append("missing_time_zero_baseline")
        if not terminal_ok: row_fail.append("terminal_time_not_85500_or_86400")
        if missing: row_fail.append("missing_internal_snapshots")
        if not monotonic: row_fail.append("coverage_non_monotonic")

        trial_dir = exp_root / "experiment-folders" / f"{benchmark}-{fuzzer}" / f"trial-{trial_id}"
        archive = latest_archive(trial_dir) if trial_dir.is_dir() else None
        members = read_members(archive) if archive else {}
        config_name, config_data = pick(members, [".adarare_config.json", "adarare_config.json"])
        bandit_name, bandit_data = pick(members, [".adarare_bandit.csv", "adarare_bandit.csv"])
        source = "standard"
        if bandit_data is None:
            bandit_name, bandit_data = pick(members, [".adarare_dbg.csv", "adarare_dbg.csv"])
            source = "debug_policy_audit_fallback"
        config = parse_config(config_data)
        selected, effective = arm_rows(bandit_data)
        if archive is None: row_fail.append("missing_terminal_corpus_archive")
        if not config: row_fail.append("missing_or_invalid_config")
        if not selected: row_fail.append("missing_arm_telemetry")

        expected = EXPECTED[fuzzer]
        policy, enable_a6, context_mode, static_arm = expected
        policy_ok = (
            config.get("policy") == policy and config.get("enable_a6") == enable_a6
            and config.get("context_mode") == context_mode
            and config.get("static_arm") == static_arm and config.get("window_ms") == 5000
        )
        if selected:
            policy_ok &= all(0 <= arm <= (5 if fuzzer == "adarare_full" else 4) for arm in selected)
            if fuzzer.startswith("adarare_static_a"):
                policy_ok &= set(selected) == {int(fuzzer.rsplit("a", 1)[1]) - 1}
            if fuzzer == "adarare_round_robin_profile":
                policy_ok &= len(selected) >= 5 and all(arm == index % 5 for index, arm in enumerate(selected))
        if effective:
            policy_ok &= all(0 <= arm <= 4 for arm in effective)
        if not policy_ok: row_fail.append("policy_or_arm_audit_failed")

        status = "PASS" if not row_fail else "FAIL"
        failures.extend(f"trial {trial_id} {benchmark}/{fuzzer}: {reason}" for reason in row_fail)
        completeness.append({
            "trial_id": trial_id, "benchmark": benchmark, "fuzzer": fuzzer,
            "trial_group_num": trial["trial_group_num"], "started": trial["time_started"] or "",
            "ended": trial["time_ended"] or "", "preempted": trial["preempted"],
            "snapshot_count": len(snaps), "status": status, "failures": ";".join(row_fail),
        })
        terminal_audit.append({
            "trial_id": trial_id, "benchmark": benchmark, "fuzzer": fuzzer,
            "pre_fuzz_coverage": initial, "terminal_time": terminal_time,
            "terminal_coverage": terminal, "missing_snapshots": ";".join(map(str, missing)),
            "coverage_monotonic": monotonic, "status": "PASS" if initial >= 0 and terminal_ok and not missing and monotonic else "FAIL",
        })
        telemetry_audit.append({
            "trial_id": trial_id, "benchmark": benchmark, "fuzzer": fuzzer,
            "archive": str(archive or ""), "config_file": config_name or "",
            "arm_file": bandit_name or "", "telemetry_source": source,
            "config_present": bool(config), "arm_rows": len(selected),
            "status": "PASS" if archive and config and selected else "FAIL",
        })
        policy_audit.append({
            "trial_id": trial_id, "benchmark": benchmark, "fuzzer": fuzzer,
            "policy": config.get("policy", ""), "enable_a6": config.get("enable_a6", ""),
            "context_mode": config.get("context_mode", ""), "static_arm": config.get("static_arm", ""),
            "window_ms": config.get("window_ms", ""),
            "selected_unique": ";".join(map(str, sorted(set(selected)))),
            "effective_unique": ";".join(map(str, sorted(set(effective)))),
            "status": "PASS" if policy_ok else "FAIL",
        })
        initial_by_cell.setdefault((benchmark, fuzzer), []).append(initial)
        if benchmark in initial_by_benchmark: initial_by_benchmark[benchmark].append(initial)

    connection.close()

    for benchmark in targets:
        values = initial_by_benchmark[benchmark]
        same = len(values) == 100 and len(set(values)) == 1
        if not same:
            failures.append(f"{benchmark}: pre-fuzz baseline differs across 100 campaigns: {sorted(set(values))}")
        hash_audit.append({
            "benchmark": benchmark, "field": "pre_fuzz_coverage",
            "distinct_count": len(set(values)), "value": ";".join(map(str, sorted(set(values)))),
            "status": "PASS" if same else "FAIL",
        })
        for field, value in frozen["binary_and_input_hashes"][benchmark].items():
            hash_audit.append({
                "benchmark": benchmark, "field": field, "distinct_count": 1,
                "value": value, "status": "PASS" if value else "FAIL",
            })

    log_path = formal_root / "logs/run_experiment.log"
    log_text = log_path.read_text(errors="replace") if log_path.is_file() else ""
    fatal_patterns = [r"failed trial", r"runner[^\n]*failed", r"measurer[^\n]*failed", r"Error conducting experiment"]
    fatal_hits = [pattern for pattern in fatal_patterns if re.search(pattern, log_text, re.I)]
    if fatal_hits:
        failures.append(f"runner/measurer fatal log patterns: {fatal_hits}")

    write_csv(formal_root / "campaign_completeness.csv", completeness)
    write_csv(formal_root / "cell_trial_counts.csv", cell_counts)
    write_csv(formal_root / "terminal_time_audit.csv", terminal_audit)
    write_csv(formal_root / "telemetry_audit.csv", telemetry_audit)
    write_csv(formal_root / "policy_audit.csv", policy_audit)
    write_csv(formal_root / "hash_equivalence.csv", hash_audit)

    report_gz = next(iter((formal_root / "reports").glob("**/data.csv.gz")), None)
    report_csv = report_gz.with_suffix("") if report_gz else None
    if report_gz and report_csv and not report_csv.exists():
        with gzip.open(report_gz, "rb") as source, report_csv.open("wb") as target:
            shutil.copyfileobj(source, target)
    if report_gz is None:
        failures.append("missing report data.csv.gz")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "# AdaRare Batch A Final Audit", "",
        f"- Formal root: `{formal_root}`", f"- Status: **{status}**",
        f"- Campaigns: **{len(trials)}/500**", f"- Cells: **{len(actual_pairs)}/50**",
        f"- Missing or failed checks: **{len(failures)}**", "",
        "## Failures", "",
    ]
    lines.extend(f"- {failure}" for failure in failures)
    if not failures: lines.append("- None")
    lines += [
        "", "## Scope", "",
        "This audit freezes completeness, terminal time, monotonic coverage, telemetry, policy/arm, and binary/corpus equivalence evidence.",
        "Statistical analysis has not been performed by this audit and the paper has not been modified.",
    ]
    final_report = formal_root / "BATCH_A_FINAL_AUDIT.md"
    final_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures:
        print(json.dumps({"status": status, "failures": failures}, indent=2))
        return 1

    host_audit = formal_root / "host_audit.txt"
    with host_audit.open("w", encoding="utf-8") as handle:
        for command in (["hostname"], ["date", "-Is"], ["uname", "-a"], ["lscpu"], ["free", "-h"], ["df", "-h", "/", "/data"]):
            handle.write(f"$ {' '.join(command)}\n")
            handle.write(subprocess.check_output(command, text=True, errors="replace"))

    sums = formal_root / "SHA256SUMS"
    files = sorted(p for p in formal_root.rglob("*") if p.is_file() and p != sums)
    with sums.open("w", encoding="utf-8") as handle:
        for path in files:
            handle.write(f"{sha256_file(path)}  {path.relative_to(formal_root)}\n")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_freeze = batch / "freeze" / f"final_{stamp}"
    final_freeze.mkdir(parents=True, exist_ok=False)
    for name in (
        "BATCH_A_FINAL_AUDIT.md", "campaign_completeness.csv", "cell_trial_counts.csv",
        "terminal_time_audit.csv", "telemetry_audit.csv", "policy_audit.csv",
        "hash_equivalence.csv", "SHA256SUMS", "host_audit.txt",
    ):
        shutil.copy2(formal_root / name, final_freeze / name)
    (final_freeze / "RESULT_LOCATION.txt").write_text(str(formal_root) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "campaigns": len(trials), "cells": len(actual_pairs),
        "formal_root": str(formal_root), "final_freeze": str(final_freeze),
        "sha256sums": str(sums), "statistics_completed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
