#!/usr/bin/env bash
set -euo pipefail

ROOT="${ADARARE_EXP_ROOT:-/data/adarare_exp}"
FB="${FUZZBENCH_DIR:-${ROOT}/fuzzbench}"
BATCH="${BATCH_A_ROOT:-${ROOT}/batch_a}"
BUILD_DIR="${1:-}"
if [[ -z "$BUILD_DIR" && -f "${BATCH}/manifests/latest_build_matrix.txt" ]]; then
  BUILD_DIR="$(<"${BATCH}/manifests/latest_build_matrix.txt")"
fi
[[ -n "$BUILD_DIR" && -f "$BUILD_DIR/summary.tsv" ]] || {
  echo "usage: canonicalize_batch_a_build_artifacts.sh [build_matrix_result_dir]" >&2
  exit 2
}

FUZZERS=(
  adarare_full adarare_linucb_no_a6 adarare_constant_context_no_a6
  adarare_random_profile adarare_round_robin_profile
  adarare_static_a1 adarare_static_a2 adarare_static_a3
  adarare_static_a4 adarare_static_a5
)
BENCHMARKS=(
  curl_curl_fuzzer_http lcms_cms_transform_fuzzer
  proj4_proj_crs_to_crs_fuzzer sqlite3_ossfuzz
  openh264_decoder_fuzzer freetype2_ftfuzzer
)
CANONICAL_FUZZER=adarare_full
CONCURRENCY="${BATCH_A_CANONICALIZE_CONCURRENCY:-2}"
BUILD_PROXY="${BATCH_A_BUILD_PROXY:-http://127.0.0.1:7890}"
MIN_DATA_FREE_KB=$((150 * 1024 * 1024))

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BUILD_DIR}/canonicalization_${STAMP}"
LOGS="${OUT}/logs"
RESULTS="${OUT}/results"
SUMMARY="${OUT}/summary.tsv"
mkdir -p "$LOGS" "$RESULTS"

check_space() {
  local free_kb
  free_kb="$(df --output=avail /data | tail -1 | tr -d ' ')"
  (( free_kb >= MIN_DATA_FREE_KB )) || {
    echo "/data free space below 150GB gate: ${free_kb}KB" >&2
    exit 1
  }
}

cd "$FB"
[[ -z "$(git status --porcelain)" ]] || {
  echo "FuzzBench worktree is not clean" >&2
  exit 1
}

reference_builder_sha="$(sha256sum "fuzzers/${CANONICAL_FUZZER}/builder.Dockerfile" | awk '{print $1}')"
reference_fuzzer_py_sha="$(sha256sum "fuzzers/${CANONICAL_FUZZER}/fuzzer.py" | awk '{print $1}')"
reference_runner_sha="$(grep -v '^ENV AFL_ADARARE_' "fuzzers/${CANONICAL_FUZZER}/runner.Dockerfile" | sha256sum | awk '{print $1}')"
for fuzzer in "${FUZZERS[@]}"; do
  [[ "$(sha256sum "fuzzers/${fuzzer}/builder.Dockerfile" | awk '{print $1}')" == "$reference_builder_sha" ]]
  [[ "$(sha256sum "fuzzers/${fuzzer}/fuzzer.py" | awk '{print $1}')" == "$reference_fuzzer_py_sha" ]]
  [[ "$(grep -v '^ENV AFL_ADARARE_' "fuzzers/${fuzzer}/runner.Dockerfile" | sha256sum | awk '{print $1}')" == "$reference_runner_sha" ]]
done

check_space
for benchmark in "${BENCHMARKS[@]}"; do
  canonical_builder="gcr.io/fuzzbench/builders/${CANONICAL_FUZZER}/${benchmark}"
  docker image inspect "$canonical_builder" >/dev/null
  for fuzzer in "${FUZZERS[@]:1}"; do
    docker image inspect "gcr.io/fuzzbench/runners/${fuzzer}/${benchmark}-intermediate" >/dev/null
    docker tag "$canonical_builder" "gcr.io/fuzzbench/builders/${fuzzer}/${benchmark}"
  done
done

run_one() {
  local benchmark="$1" fuzzer="$2"
  local start end duration rc status log result runner
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log="${LOGS}/${benchmark}__${fuzzer}.log"
  result="${RESULTS}/${benchmark}__${fuzzer}.tsv"
  runner="gcr.io/fuzzbench/runners/${fuzzer}/${benchmark}"
  set +e
  docker build \
    --network=host \
    --tag "$runner" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --cache-from "$runner" \
    --build-arg "HTTP_PROXY=${BUILD_PROXY}" \
    --build-arg "HTTPS_PROXY=${BUILD_PROXY}" \
    --build-arg "http_proxy=${BUILD_PROXY}" \
    --build-arg "https_proxy=${BUILD_PROXY}" \
    --build-arg "NO_PROXY=localhost,127.0.0.1,::1" \
    --build-arg "no_proxy=localhost,127.0.0.1,::1" \
    --build-arg "benchmark=${benchmark}" \
    --build-arg "fuzzer=${fuzzer}" \
    --file docker/benchmark-runner/Dockerfile \
    . >"$log" 2>&1
  rc=$?
  set -e
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  duration=$(( $(date -d "$end" +%s) - $(date -d "$start" +%s) ))
  status=PASS
  (( rc == 0 )) || status=FAIL
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$benchmark" "$fuzzer" "$start" "$end" "$duration" "$rc" "$status" "$log" > "$result"
}

running=0
for benchmark in "${BENCHMARKS[@]}"; do
  for fuzzer in "${FUZZERS[@]:1}"; do
    check_space
    run_one "$benchmark" "$fuzzer" &
    ((running += 1))
    if (( running >= CONCURRENCY )); then
      wait -n || true
      running=$((running - 1))
    fi
  done
done
while (( running > 0 )); do
  wait -n || true
  running=$((running - 1))
done

printf 'benchmark\tfuzzer\tstart_time\tend_time\tduration_sec\texit_code\tstatus\tlog_path\n' > "$SUMMARY"
find "$RESULTS" -type f -name '*.tsv' -print0 | sort -z | xargs -0 cat >> "$SUMMARY"
records="$(tail -n +2 "$SUMMARY" | wc -l | tr -d ' ')"
failures="$(tail -n +2 "$SUMMARY" | awk -F '\t' '$7 != "PASS" {count++} END {print count+0}')"
{
  echo "records=${records}"
  echo "failures=${failures}"
  df -h / /data
} > "${OUT}/status.txt"
printf '%s\n' "$OUT" > "${BATCH}/manifests/latest_build_canonicalization.txt"
[[ "$records" == 54 && "$failures" == 0 ]] || {
  echo "canonicalization failed: records=${records} failures=${failures}" >&2
  exit 1
}
echo "CANONICALIZATION_GATE=PASS" >> "${OUT}/status.txt"
cat "${OUT}/status.txt"
