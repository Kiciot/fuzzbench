#!/usr/bin/env python3
"""Audit Batch A one-hour FuzzBench stages without relaxing any gate."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import tarfile
from typing import Any

FUZZERS = [
    "adarare_full", "adarare_linucb_no_a6",
    "adarare_constant_context_no_a6", "adarare_random_profile",
    "adarare_round_robin_profile", "adarare_static_a1",
    "adarare_static_a2", "adarare_static_a3", "adarare_static_a4",
    "adarare_static_a5",
]
STAGE_BENCHMARKS = {
    "curl": ["curl_curl_fuzzer_http"],
    "core-rest": ["lcms_cms_transform_fuzzer", "proj4_proj_crs_to_crs_fuzzer",
                  "sqlite3_ossfuzz", "openh264_decoder_fuzzer"],
    "fallback-five": ["lcms_cms_transform_fuzzer", "proj4_proj_crs_to_crs_fuzzer",
                      "sqlite3_ossfuzz", "openh264_decoder_fuzzer",
                      "freetype2_ftfuzzer"],
}
EXPECTED = {
    "adarare_full": ("linucb", 1, "dynamic", None),
    "adarare_linucb_no_a6": ("linucb", 0, "dynamic", None),
    "adarare_constant_context_no_a6": ("linucb", 0, "constant", None),
    "adarare_random_profile": ("random_profile", 0, "dynamic", None),
    "adarare_round_robin_profile": ("round_robin_profile", 0, "dynamic", None),
    **{f"adarare_static_a{i}": ("static_profile", 0, "dynamic", i) for i in range(1, 6)},
}
HASH_FIELDS = [
    "target_binary_sha256", "coverage_binary_sha256",
    "cmplog_binary_sha256", "initial_corpus_manifest_sha256",
    "dictionary_manifest_sha256",
]


def latest_archive(trial_dir: Path) -> Path | None:
    archives = archives_in_order(trial_dir)
    if not archives:
        return None
    return archives[-1]


def archive_number(path: Path) -> int:
    match = re.search(r"(\d+)\.tar\.gz$", path.name)
    return int(match.group(1)) if match else -1


def archives_in_order(trial_dir: Path) -> list[Path]:
    return sorted(
        (trial_dir / "corpus-archives").glob("corpus-archive-*.tar.gz"),
        key=archive_number,
    )


def read_members(archive: Path) -> dict[str, bytes]:
    wanted = {
        ".adarare_config.json", "adarare_config.json",
        ".adarare_bandit.csv", "adarare_bandit.csv",
        ".adarare_dbg.csv", "adarare_dbg.csv", "fuzzer_stats",
    }
    result: dict[str, bytes] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or Path(member.name).name not in wanted:
                continue
            extracted = tar.extractfile(member)
            if extracted is not None:
                result[Path(member.name).name] = extracted.read()
    return result


def read_trial_members(trial_dir: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Reconstruct metadata from incremental corpus archives.

    FuzzBench archives contain only files modified since the previous sync.
    Configuration commonly appears only in the first runtime archive, while
    stats and debug telemetry are updated later.  Read every archive in cycle
    order and retain the newest occurrence of each member.
    """
    result: dict[str, bytes] = {}
    sources: dict[str, str] = {}
    for archive in archives_in_order(trial_dir):
        for name, data in read_members(archive).items():
            result[name] = data
            sources[name] = archive.name
    return result, sources


def archive_file_count(archive: Path | None) -> int:
    if archive is None:
        return -1
    try:
        with tarfile.open(archive, "r:gz") as tar:
            return sum(1 for member in tar if member.isfile())
    except (OSError, tarfile.TarError):
        return -1


def pick(members: dict[str, bytes], names: list[str]) -> tuple[str, bytes] | tuple[None, None]:
    for name in names:
        if name in members:
            return name, members[name]
    return None, None


def stats_dict(data: bytes | None) -> dict[str, str]:
    if not data:
        return {}
    result = {}
    for line in data.decode("utf-8", "replace").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            result[key.strip()] = value.strip()
    return result


def int_value(stats: dict[str, str], *keys: str) -> int:
    for key in keys:
        value = stats.get(key)
        if value is not None:
            try:
                return int(value.split()[0])
            except ValueError:
                pass
    return -1


def arm_rows(data: bytes | None) -> tuple[list[int], list[int]]:
    if not data:
        return [], []
    selected: list[int] = []
    effective: list[int] = []
    reader = csv.DictReader(io.StringIO(data.decode("utf-8", "replace")))
    for row in reader:
        for key in ("arm_id", "selected_arm", "arm"):
            if row.get(key) not in (None, ""):
                try:
                    selected.append(int(float(row[key])))
                except ValueError:
                    pass
                break
        for key in ("effective_arm", "a6_eff_arm"):
            if row.get(key) not in (None, ""):
                try:
                    effective.append(int(float(row[key])))
                except ValueError:
                    pass
                break
    return selected, effective


def debug_arm_rows(data: bytes | None) -> tuple[list[int], list[int]]:
    """Parse policy-only evidence from AdaRare's debug fallback."""
    if not data:
        return [], []
    selected: list[int] = []
    effective: list[int] = []
    for line in data.decode("utf-8", "replace").splitlines():
        if not line.startswith("[bandit dbg] policy="):
            continue
        fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
        try:
            selected.append(int(fields["arm_cur"]))
            effective.append(int(fields["arm_eff"]))
        except (KeyError, ValueError):
            continue
    return selected, effective


def select_arm_telemetry(
        members: dict[str, bytes]) -> tuple[str | None, list[int], list[int], str]:
    """Prefer standard telemetry, but use richer debug policy evidence.

    The fallback is used only for policy/context/arm auditing.  Coverage,
    reward, and performance values never come from the debug log.
    """
    standard_name, standard_data = pick(
        members, [".adarare_bandit.csv", "adarare_bandit.csv"])
    debug_name, debug_data = pick(
        members, [".adarare_dbg.csv", "adarare_dbg.csv"])
    standard_selected, standard_effective = arm_rows(standard_data)
    debug_selected, debug_effective = debug_arm_rows(debug_data)
    if len(debug_selected) > len(standard_selected):
        return (debug_name, debug_selected, debug_effective,
                "debug_policy_audit_fallback")
    return (standard_name, standard_selected, standard_effective, "standard")


def find_db(stage_dir: Path) -> Path | None:
    candidate = stage_dir / "experiment-data" / "local.db"
    return candidate if candidate.is_file() else None


def experiment_root(stage_dir: Path) -> Path | None:
    base = stage_dir / "experiment-data"
    dirs = [p for p in base.iterdir() if p.is_dir()] if base.is_dir() else []
    dirs = [p for p in dirs if (p / "experiment-folders").is_dir()]
    return dirs[0] if len(dirs) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    provenance_marker = Path("/data/adarare_exp/batch_a/manifests/latest_build_provenance.txt")
    provenance_dir = Path(provenance_marker.read_text(encoding="utf-8").strip())
    with (provenance_dir / "build_provenance.tsv").open(newline="", encoding="utf-8") as handle:
        provenance = list(csv.DictReader(handle, delimiter="\t"))
    seed_counts = {row["benchmark"]: int(row["seed_file_count"]) for row in provenance}

    summary: list[dict[str, Any]] = []
    policy_audit: list[dict[str, Any]] = []
    hash_audit: list[dict[str, Any]] = []
    stage_status: dict[str, str] = {}
    stage_failures: dict[str, list[str]] = {}

    for stage, expected_benchmarks in STAGE_BENCHMARKS.items():
        stage_dir = root / stage
        db_path = find_db(stage_dir)
        if db_path is None:
            continue
        failures: list[str] = []
        runtime_image_path = stage_dir / "runtime_image_audit.tsv"
        runtime_images: list[dict[str, str]] = []
        if runtime_image_path.is_file():
            with runtime_image_path.open(newline="", encoding="utf-8") as handle:
                runtime_images = list(csv.DictReader(handle, delimiter="\t"))
        expected_runtime_rows = len(expected_benchmarks) * len(FUZZERS)
        if (len(runtime_images) != expected_runtime_rows or
                any(row.get("status") != "PASS" for row in runtime_images)):
            failures.append(
                f"runtime image audit mismatch expected={expected_runtime_rows} "
                f"actual={len(runtime_images)}")
        exp_root = experiment_root(stage_dir)
        if exp_root is None:
            failures.append("cannot uniquely locate experiment-folders root")

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        trials = list(connection.execute(
            "select id,fuzzer,benchmark,time_started,time_ended,preempted,trial_group_num from trial order by benchmark,fuzzer,id"
        ))
        expected_pairs = {(b, f) for b in expected_benchmarks for f in FUZZERS}
        actual_pairs = {(row["benchmark"], row["fuzzer"]) for row in trials}
        if len(trials) != len(expected_pairs) or actual_pairs != expected_pairs:
            failures.append(
                f"trial matrix mismatch expected={len(expected_pairs)} actual={len(trials)} "
                f"missing={sorted(expected_pairs-actual_pairs)} extra={sorted(actual_pairs-expected_pairs)}"
            )

        initial_by_benchmark: dict[str, list[int]] = {b: [] for b in expected_benchmarks}
        terminal_by_benchmark: dict[str, list[int]] = {b: [] for b in expected_benchmarks}
        for trial in trials:
            benchmark, fuzzer, trial_id = trial["benchmark"], trial["fuzzer"], trial["id"]
            snaps = list(connection.execute(
                "select time,edges_covered from snapshot where trial_id=? order by time", (trial_id,)
            ))
            times = [int(row["time"]) for row in snaps]
            coverages = [int(row["edges_covered"]) for row in snaps]
            initial = coverages[0] if times and times[0] == 0 else -1
            terminal = coverages[-1] if coverages else -1
            terminal_time = times[-1] if times else -1
            monotonic = all(a <= b for a, b in zip(coverages, coverages[1:]))
            if benchmark in initial_by_benchmark and initial >= 0:
                initial_by_benchmark[benchmark].append(initial)
                terminal_by_benchmark[benchmark].append(terminal)

            trial_dir = exp_root / "experiment-folders" / f"{benchmark}-{fuzzer}" / f"trial-{trial_id}" if exp_root else Path("/missing")
            archive = latest_archive(trial_dir) if trial_dir.is_dir() else None
            members, member_sources = read_trial_members(trial_dir) if trial_dir.is_dir() else ({}, {})
            terminal_cycle = terminal_time // 900 if terminal_time >= 0 else -1
            terminal_archive = (trial_dir / "corpus-archives" /
                                f"corpus-archive-{terminal_cycle:04d}.tar.gz")
            if not terminal_archive.is_file():
                terminal_archive = None
            terminal_archive_files = archive_file_count(terminal_archive)
            _, stats_data = pick(members, ["fuzzer_stats"])
            stats = stats_dict(stats_data)
            execs_done = int_value(stats, "execs_done")
            corpus_count = int_value(stats, "corpus_count", "paths_total")
            queue_growth = corpus_count > seed_counts.get(benchmark, 0)

            row_failures = []
            if trial["time_started"] is None or trial["time_ended"] is None or trial["preempted"]:
                row_failures.append("runner_not_cleanly_completed")
            if initial < 0 or terminal_time < 3600:
                row_failures.append("missing_time0_or_3600_coverage")
            if not monotonic:
                row_failures.append("coverage_non_monotonic")
            if archive is None:
                row_failures.append("missing_corpus_archive")
            if terminal_archive_files <= 0:
                row_failures.append("missing_or_empty_terminal_corpus_archive")
            if execs_done <= 0:
                row_failures.append("execs_done_not_positive")
            if not queue_growth:
                row_failures.append("queue_did_not_grow_beyond_initial_corpus")

            config_name, config_data = pick(members, [".adarare_config.json", "adarare_config.json"])
            bandit_name, selected, effective, telemetry_source = select_arm_telemetry(members)
            config: dict[str, Any] = {}
            if config_data:
                try:
                    config = json.loads(config_data)
                except json.JSONDecodeError:
                    row_failures.append("invalid_config_json")
            else:
                row_failures.append("missing_adarare_config")
            if not selected:
                row_failures.append("missing_policy_arm_telemetry")
            expected_windows = terminal_time * 1000 // 5000 if terminal_time > 0 else 0
            minimum_windows = max(5, expected_windows * 9 // 10)
            if len(selected) < minimum_windows:
                row_failures.append(
                    f"incomplete_policy_arm_telemetry:{len(selected)}<{minimum_windows}")

            expected = EXPECTED.get(fuzzer)
            policy_ok = bool(expected)
            if expected:
                policy, enable_a6, context_mode, static_arm = expected
                policy_ok = (
                    config.get("policy") == policy
                    and config.get("enable_a6") == enable_a6
                    and config.get("context_mode") == context_mode
                    and config.get("static_arm") == static_arm
                    and config.get("window_ms") == 5000
                )
                if selected:
                    if fuzzer == "adarare_full":
                        policy_ok = policy_ok and all(0 <= arm <= 5 for arm in selected)
                    else:
                        policy_ok = policy_ok and all(0 <= arm <= 4 for arm in selected)
                    if fuzzer.startswith("adarare_static_a"):
                        exact = int(fuzzer.rsplit("a", 1)[1]) - 1
                        policy_ok = policy_ok and set(selected) == {exact}
                    if fuzzer == "adarare_round_robin_profile":
                        policy_ok = policy_ok and len(selected) >= 5 and all(
                            arm == index % 5 for index, arm in enumerate(selected)
                        )
                if effective:
                    policy_ok = policy_ok and all(0 <= arm <= 4 for arm in effective)
            if not policy_ok:
                row_failures.append("policy_or_arm_audit_failed")

            status = "PASS" if not row_failures else "FAIL"
            failures.extend(f"{benchmark}/{fuzzer}: {item}" for item in row_failures)
            summary.append({
                "stage": stage, "benchmark": benchmark, "fuzzer": fuzzer,
                "trial_id": trial_id, "runner_status": "PASS" if trial["time_ended"] and not trial["preempted"] else "FAIL",
                "snapshot_count": len(snaps), "pre_fuzz_coverage": initial,
                "terminal_time": terminal_time, "terminal_coverage": terminal,
                "coverage_monotonic": monotonic, "execs_done": execs_done,
                "corpus_count": corpus_count, "initial_seed_count": seed_counts.get(benchmark, -1),
                "queue_growth": queue_growth, "status": status,
                "failures": ";".join(row_failures), "archive": str(archive or ""),
                "terminal_archive": str(terminal_archive or ""),
                "terminal_archive_files": terminal_archive_files,
            })
            policy_audit.append({
                "stage": stage, "benchmark": benchmark, "fuzzer": fuzzer,
                "trial_id": trial_id, "telemetry_source": telemetry_source,
                "config_file": config_name or "", "arm_file": bandit_name or "",
                "config_archive": member_sources.get(config_name or "", ""),
                "arm_archive": member_sources.get(bandit_name or "", ""),
                "arm_rows": len(selected),
                "policy": config.get("policy", ""), "enable_a6": config.get("enable_a6", ""),
                "context_mode": config.get("context_mode", ""),
                "static_arm": config.get("static_arm", ""), "window_ms": config.get("window_ms", ""),
                "selected_min": min(selected) if selected else "", "selected_max": max(selected) if selected else "",
                "selected_unique": ",".join(map(str, sorted(set(selected)))),
                "effective_unique": ",".join(map(str, sorted(set(effective)))),
                "status": "PASS" if policy_ok else "FAIL",
            })

        for benchmark, values in initial_by_benchmark.items():
            same = len(values) == 10 and len(set(values)) == 1
            if not same:
                failures.append(f"{benchmark}: deterministic pre-fuzz coverage mismatch {values}")
            if benchmark == "curl_curl_fuzzer_http" and (not same or not 6000 <= values[0] <= 8000):
                failures.append(f"curl pre-fuzz coverage outside fixed 6000-8000 gate: {values}")
            terminals = terminal_by_benchmark[benchmark]
            if len(terminals) == 10 and all(t <= i for t, i in zip(terminals, values)):
                failures.append(f"{benchmark}: all ten variants show no coverage growth")

            p_rows = [row for row in provenance if row["benchmark"] == benchmark]
            for field in HASH_FIELDS:
                distinct = sorted({row[field] for row in p_rows})
                ok = len(p_rows) == 10 and len(distinct) == 1 and bool(distinct[0])
                hash_audit.append({
                    "stage": stage, "benchmark": benchmark, "field": field,
                    "distinct_count": len(distinct), "value": "|".join(distinct),
                    "status": "PASS" if ok else "FAIL",
                })
                if not ok:
                    failures.append(f"{benchmark}: build hash field {field} is not equivalent")
            for image_row in sorted(
                    (row for row in runtime_images if row["benchmark"] == benchmark),
                    key=lambda row: row["fuzzer"]):
                hash_audit.append({
                    "stage": stage, "benchmark": benchmark,
                    "field": f"runner_image_id:{image_row['fuzzer']}",
                    "distinct_count": 1,
                    "value": image_row["actual_image_id"],
                    "status": image_row["status"],
                })
            hash_audit.append({
                "stage": stage, "benchmark": benchmark, "field": "pre_fuzz_coverage",
                "distinct_count": len(set(values)), "value": "|".join(map(str, sorted(set(values)))),
                "status": "PASS" if same else "FAIL",
            })

        connection.close()
        log_path = stage_dir / "logs/run_experiment.log"
        log_text = log_path.read_text(errors="replace") if log_path.is_file() else ""
        coverage_failures = len(re.findall(r"Coverage run failed", log_text))
        if coverage_failures:
            failures.append(f"coverage_run_failures={coverage_failures}")
        stage_status[stage] = "PASS" if not failures else "FAIL"
        stage_failures[stage] = failures

    def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            path.write_text("status\n", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    write_tsv(root / "quality_gate_summary.tsv", summary)
    write_tsv(root / "quality_gate_hash_audit.tsv", hash_audit)
    write_tsv(root / "quality_gate_policy_audit.tsv", policy_audit)

    curl_status = stage_status.get("curl", "NOT_RUN")
    if curl_status == "PASS" and stage_status.get("core-rest") == "PASS":
        formal_targets = ["curl_curl_fuzzer_http", *STAGE_BENCHMARKS["core-rest"]]
        ready = True
        fallback_used = False
    elif curl_status == "FAIL" and stage_status.get("fallback-five") == "PASS":
        formal_targets = STAGE_BENCHMARKS["fallback-five"]
        ready = True
        fallback_used = True
    else:
        formal_targets = []
        ready = False
        fallback_used = curl_status == "FAIL"

    decision = {
        "status": "PASS" if ready else "INCOMPLETE_OR_FAIL",
        "curl_status": curl_status,
        "stage_status": stage_status,
        "stage_failures": stage_failures,
        "fallback_used": fallback_used,
        "formal_targets": formal_targets,
        "formal_ready": ready,
        "curl_initial_coverage_gate": [6000, 8000],
    }
    (root / "quality_gate_decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# AdaRare Batch A Quality Gate Audit", "",
        f"- Quality root: `{root}`",
        f"- Curl status: **{curl_status}**",
        f"- Freetype2 fallback selected: **{fallback_used}**",
        f"- Formal-ready: **{ready}**",
        f"- Formal targets: `{', '.join(formal_targets) if formal_targets else 'not frozen'}`",
        "", "## Stage results", "",
    ]
    for stage in STAGE_BENCHMARKS:
        lines.append(f"- `{stage}`: {stage_status.get(stage, 'NOT_RUN')}")
        for failure in stage_failures.get(stage, []):
            lines.append(f"  - FAIL: {failure}")
    lines += [
        "", "## Gate interpretation", "",
        "The time-zero snapshot is the deterministic pre-fuzz coverage baseline; the first 900-second snapshot is not called initial coverage.",
        "`.adarare_dbg.csv` is accepted only as a policy/arm audit fallback and is not used for reward, coverage, or performance statistics.",
        "Curl uses the preregistered 6000-8000 pre-fuzz coverage interval. This threshold is not modified after observing the run.",
    ]
    (root / "BATCH_A_QUALITY_GATE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, sort_keys=True))
    later_stage_attempted = "core-rest" in stage_status or "fallback-five" in stage_status
    return 0 if ready or not later_stage_attempted else 1


if __name__ == "__main__":
    raise SystemExit(main())
