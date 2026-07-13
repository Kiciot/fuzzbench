"""Focused tests for strict Batch A quality-audit evidence handling."""

import io
from pathlib import Path
import tarfile

from audit_batch_a_quality_gate import (
    archive_file_count,
    debug_arm_rows,
    read_trial_members,
    select_arm_telemetry,
)


def _write_archive(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_read_trial_members_reconstructs_incremental_archives(tmp_path):
    archive_dir = tmp_path / "corpus-archives"
    _write_archive(archive_dir / "corpus-archive-0001.tar.gz", {
        "default/.adarare_config.json": b'{"policy":"linucb"}',
        "default/fuzzer_stats": b"execs_done : 10\n",
    })
    _write_archive(archive_dir / "corpus-archive-0002.tar.gz", {
        "default/fuzzer_stats": b"execs_done : 20\n",
    })

    members, sources = read_trial_members(tmp_path)

    assert members[".adarare_config.json"] == b'{"policy":"linucb"}'
    assert members["fuzzer_stats"] == b"execs_done : 20\n"
    assert sources[".adarare_config.json"] == "corpus-archive-0001.tar.gz"
    assert sources["fuzzer_stats"] == "corpus-archive-0002.tar.gz"


def test_debug_fallback_parses_only_policy_decisions():
    data = b"\n".join([
        b"[bandit dbg] policy=round_robin_profile arm_cur=0 arm_eff=0",
        b"[bandit dbg] reward final_reward=1.0",
        b"[bandit dbg] policy=round_robin_profile arm_cur=1 arm_eff=1",
    ])
    assert debug_arm_rows(data) == ([0, 1], [0, 1])


def test_richer_debug_evidence_replaces_sparse_standard_csv():
    members = {
        ".adarare_bandit.csv": b"arm_id,effective_arm\n0,0\n",
        ".adarare_dbg.csv": b"\n".join(
            f"[bandit dbg] policy=round_robin_profile arm_cur={i} arm_eff={i}".encode()
            for i in range(5)
        ),
    }
    name, selected, effective, source = select_arm_telemetry(members)
    assert name == ".adarare_dbg.csv"
    assert selected == [0, 1, 2, 3, 4]
    assert effective == selected
    assert source == "debug_policy_audit_fallback"


def test_empty_terminal_archive_is_detected(tmp_path):
    archive = tmp_path / "corpus-archive-0004.tar.gz"
    _write_archive(archive, {})
    assert archive_file_count(archive) == 0
