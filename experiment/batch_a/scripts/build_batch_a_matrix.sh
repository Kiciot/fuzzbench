#!/usr/bin/env bash
set -uo pipefail

ROOT="${ADARARE_EXP_ROOT:-/data/adarare_exp}"
FB="${FUZZBENCH_DIR:-${ROOT}/fuzzbench}"
BATCH="${BATCH_A_ROOT:-${ROOT}/batch_a}"
CONCURRENCY="${BATCH_A_BUILD_CONCURRENCY:-2}"
MAKE_JOBS="${BATCH_A_MAKE_JOBS:-1}"
MIN_ROOT_GB="${BATCH_A_MIN_ROOT_FREE_GB:-50}"
MIN_DATA_GB="${BATCH_A_MIN_DATA_FREE_GB:-150}"
BUILD_PROXY="${BATCH_A_BUILD_PROXY:-http://127.0.0.1:7890}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BATCH}/results/build_matrix_${TS}"
LOGS="${OUT}/logs"
SUMMARY="${OUT}/summary.tsv"
COVERAGE_SUMMARY="${OUT}/coverage_build_summary.tsv"
STOP_FILE="${OUT}/STOP_DISK_GATE"

FUZZERS=(
  adarare_full
  adarare_linucb_no_a6
  adarare_constant_context_no_a6
  adarare_random_profile
  adarare_round_robin_profile
  adarare_static_a1
  adarare_static_a2
  adarare_static_a3
  adarare_static_a4
  adarare_static_a5
)
BENCHMARKS=(
  curl_curl_fuzzer_http
  lcms_cms_transform_fuzzer
  proj4_proj_crs_to_crs_fuzzer
  sqlite3_ossfuzz
  openh264_decoder_fuzzer
  freetype2_ftfuzzer
)

usage() {
  cat <<'EOF'
Usage: build_batch_a_matrix.sh

Builds six coverage images plus the clean 6 benchmark x 10 variant matrix.
The six coverage builds are infrastructure prerequisites and are reported
separately; summary.tsv contains exactly the required 60 variant builds.

Environment overrides:
  BATCH_A_BUILD_CONCURRENCY (default 2)
  BATCH_A_MAKE_JOBS         (default 1 per make target)
  BATCH_A_MIN_ROOT_FREE_GB  (default 50)
  BATCH_A_MIN_DATA_FREE_GB  (default 150)
  BATCH_A_BUILD_PROXY       (default http://127.0.0.1:7890)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if (( $# != 0 )); then
  echo "unexpected arguments: $*" >&2
  usage >&2
  exit 2
fi

for value in "$CONCURRENCY" "$MAKE_JOBS" "$MIN_ROOT_GB" "$MIN_DATA_GB"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || { echo "invalid positive integer: $value" >&2; exit 2; }
done

mkdir -p "$LOGS" "${BATCH}/manifests"
mkdir -p "${OUT}/locks"
[[ -z "$(git -C "$FB" status --porcelain)" ]] || {
  echo "FuzzBench worktree is not clean" >&2
  exit 1
}
FB_COMMIT="$(git -C "$FB" rev-parse HEAD)"
FB_UPSTREAM_COMMIT="$(git -C "$FB" rev-parse '@{upstream}')"
[[ "$FB_COMMIT" == "$FB_UPSTREAM_COMMIT" ]] || {
  echo "FuzzBench HEAD does not match upstream" >&2
  exit 1
}
{
  echo "fuzzbench_commit=$FB_COMMIT"
  echo "fuzzbench_upstream_commit=$FB_UPSTREAM_COMMIT"
  echo "worktree_clean=true"
} > "${OUT}/repo_state.txt"
printf 'benchmark\tfuzzer\tmake_target\tstart_time\tend_time\tduration_sec\texit_code\tstatus\tlog_path\n' > "$SUMMARY"
printf 'benchmark\tmake_target\tstart_time\tend_time\tduration_sec\texit_code\tstatus\tlog_path\n' > "$COVERAGE_SUMMARY"
printf '%s\n' "$OUT" > "${BATCH}/manifests/latest_build_matrix.txt"

exec 9>"${OUT}/summary.lock"

free_gb() {
  df -BG --output=avail "$1" | awk 'NR==2 {gsub(/G/, "", $1); print $1+0}'
}

disk_gate() {
  local root_free data_free
  root_free="$(free_gb /)"
  data_free="$(free_gb /data)"
  if (( root_free < MIN_ROOT_GB || data_free < MIN_DATA_GB )); then
    printf 'root_free_gb=%s min_root_gb=%s data_free_gb=%s min_data_gb=%s\n' \
      "$root_free" "$MIN_ROOT_GB" "$data_free" "$MIN_DATA_GB" | tee "$STOP_FILE" >&2
    return 1
  fi
}

build_args() {
  printf '%s' "--network=host --build-arg HTTP_PROXY=${BUILD_PROXY} --build-arg HTTPS_PROXY=${BUILD_PROXY} --build-arg http_proxy=${BUILD_PROXY} --build-arg https_proxy=${BUILD_PROXY} --build-arg NO_PROXY=localhost,127.0.0.1,::1 --build-arg no_proxy=localhost,127.0.0.1,::1"
}

run_coverage() {
  local benchmark="$1" target="build-coverage-${1}"
  local log="${LOGS}/coverage_${benchmark}.log" start end duration rc status
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local start_epoch="$(date +%s)"
  {
    echo "[$start] START $target"
    df -h / /data
  } > "$log"
  if ! disk_gate >>"$log" 2>&1; then
    rc=98
  else
    (
      cd "$FB" || exit 97
      ADARARE_DOCKER_BUILD_ARGS="$(build_args)" make -j"$MAKE_JOBS" -o base-image "$target"
    ) >>"$log" 2>&1
    rc=$?
  fi
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  duration=$(( $(date +%s) - start_epoch ))
  (( rc == 0 )) && status=PASS || status=FAIL
  echo "[$end] END $target rc=$rc status=$status duration_sec=$duration" >> "$log"
  flock 9
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$benchmark" "$target" "$start" "$end" "$duration" "$rc" "$status" "$log" >> "$COVERAGE_SUMMARY"
  flock -u 9
  return 0
}

run_one() {
  local benchmark="$1" fuzzer="$2" target="build-${2}-${1}"
  local log="${LOGS}/${benchmark}__${fuzzer}.log" start end duration rc status
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local start_epoch="$(date +%s)"
  {
    echo "[$start] START $target"
    echo "fuzzbench_head=$(git -C "$FB" rev-parse HEAD)"
    echo "root_free_gb=$(free_gb /) data_free_gb=$(free_gb /data)"
  } > "$log"
  if [[ -e "$STOP_FILE" ]] || ! disk_gate >>"$log" 2>&1; then
    rc=98
  else
    local bench_lock_fd
    exec {bench_lock_fd}>"${OUT}/locks/${benchmark}.lock"
    flock "$bench_lock_fd"
    (
      cd "$FB" || exit 97
      ADARARE_DOCKER_BUILD_ARGS="$(build_args)" make -j"$MAKE_JOBS" -o base-image "$target"
    ) >>"$log" 2>&1
    rc=$?
    flock -u "$bench_lock_fd"
    exec {bench_lock_fd}>&-
  fi
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  duration=$(( $(date +%s) - start_epoch ))
  (( rc == 0 )) && status=PASS || status=FAIL
  echo "[$end] END $target rc=$rc status=$status duration_sec=$duration" >> "$log"
  flock 9
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$benchmark" "$fuzzer" "$target" "$start" "$end" "$duration" "$rc" "$status" "$log" >> "$SUMMARY"
  flock -u 9
  return 0
}

wait_for_slot() {
  while (( $(jobs -pr | wc -l) >= CONCURRENCY )); do
    wait -n || true
  done
}

echo "output=$OUT"
echo "coverage_builds=${#BENCHMARKS[@]} matrix_builds=$((${#BENCHMARKS[@]} * ${#FUZZERS[@]})) concurrency=$CONCURRENCY"

BASE_LOG="${LOGS}/base_image.log"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START base-image" > "$BASE_LOG"
if ! disk_gate >>"$BASE_LOG" 2>&1; then
  echo "BASE_IMAGE_GATE=FAIL reason=disk_gate" | tee -a "$BASE_LOG" "${OUT}/status.txt" >&2
  exit 1
fi
(
  cd "$FB" || exit 97
  ADARARE_DOCKER_BUILD_ARGS="$(build_args)" make -j1 base-image
) >>"$BASE_LOG" 2>&1
base_rc=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] END base-image rc=$base_rc" >> "$BASE_LOG"
if (( base_rc != 0 )); then
  echo "BASE_IMAGE_GATE=FAIL rc=$base_rc" | tee -a "${OUT}/status.txt" >&2
  exit 1
fi
echo "BASE_IMAGE_GATE=PASS" >> "$BASE_LOG"

for benchmark in "${BENCHMARKS[@]}"; do
  [[ -e "$STOP_FILE" ]] && break
  wait_for_slot
  run_coverage "$benchmark" &
done
wait || true

coverage_failures="$(awk -F '\t' 'NR>1 && $7!="PASS" {n++} END {print n+0}' "$COVERAGE_SUMMARY")"
coverage_records="$(awk 'END {print NR-1}' "$COVERAGE_SUMMARY")"
if (( coverage_failures != 0 || coverage_records != 6 )); then
  echo "coverage prerequisite gate failed: records=$coverage_records failures=$coverage_failures" | tee "${OUT}/status.txt" >&2
  exit 1
fi

for fuzzer in "${FUZZERS[@]}"; do
  for benchmark in "${BENCHMARKS[@]}"; do
    [[ -e "$STOP_FILE" ]] && break 2
    wait_for_slot
    run_one "$benchmark" "$fuzzer" &
  done
done
wait || true

records="$(awk 'END {print NR-1}' "$SUMMARY")"
failures="$(awk -F '\t' 'NR>1 && ($7!=0 || $8!="PASS") {n++} END {print n+0}' "$SUMMARY")"
core_records="$(awk -F '\t' 'NR>1 && $1!="freetype2_ftfuzzer" {n++} END {print n+0}' "$SUMMARY")"
core_pass="$(awk -F '\t' 'NR>1 && $1!="freetype2_ftfuzzer" && $8=="PASS" {n++} END {print n+0}' "$SUMMARY")"
fallback_pass="$(awk -F '\t' 'NR>1 && $1=="freetype2_ftfuzzer" && $8=="PASS" {n++} END {print n+0}' "$SUMMARY")"
{
  echo "fuzzbench_commit=$FB_COMMIT"
  echo "records=$records"
  echo "failures=$failures"
  echo "core_records=$core_records"
  echo "core_pass=$core_pass"
  echo "fallback_pass=$fallback_pass"
  echo "coverage_pass=$((6 - coverage_failures))"
  df -h / /data
} | tee "${OUT}/status.txt"

if (( records != 60 || failures != 0 || core_records != 50 || core_pass != 50 || fallback_pass != 10 )); then
  exit 1
fi
echo "BUILD_MATRIX_GATE=PASS" | tee -a "${OUT}/status.txt"
