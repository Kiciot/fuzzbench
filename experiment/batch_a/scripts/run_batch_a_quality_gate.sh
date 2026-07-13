#!/usr/bin/env bash
set -euo pipefail

ROOT="${ADARARE_EXP_ROOT:-/data/adarare_exp}"
FB="${FUZZBENCH_DIR:-${ROOT}/fuzzbench}"
BATCH="${BATCH_A_ROOT:-${ROOT}/batch_a}"
CONFIG_TEMPLATE="${BATCH}/configs/batch_a_quality_gate.yaml"
STAGE="${1:-}"
FUZZERS=(
  adarare_full adarare_linucb_no_a6 adarare_constant_context_no_a6
  adarare_random_profile adarare_round_robin_profile
  adarare_static_a1 adarare_static_a2 adarare_static_a3
  adarare_static_a4 adarare_static_a5
)
CORE_REST=(
  lcms_cms_transform_fuzzer proj4_proj_crs_to_crs_fuzzer
  sqlite3_ossfuzz openh264_decoder_fuzzer
)
FALLBACK_FIVE=(
  lcms_cms_transform_fuzzer proj4_proj_crs_to_crs_fuzzer
  sqlite3_ossfuzz openh264_decoder_fuzzer freetype2_ftfuzzer
)

usage() {
  cat <<'EOF'
Usage: run_batch_a_quality_gate.sh curl|core-rest|fallback-five

Run `curl` first. Run `core-rest` only after the curl audit passes. If curl
fails, preserve it and run `fallback-five`; no threshold is changed.
EOF
}
[[ "$STAGE" =~ ^(curl|core-rest|fallback-five)$ ]] || { usage >&2; exit 2; }

PROV_DIR="$(<"${BATCH}/manifests/latest_build_provenance.txt")"
python3 - "$PROV_DIR/hash_equivalence.json" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p, encoding='utf-8'))
if d.get('status') != 'PASS':
    raise SystemExit(f'hash equivalence gate is not PASS: {p}')
PY

cd "$FB"
[[ -z "$(git status --porcelain)" ]] || { echo "FuzzBench working tree is not clean" >&2; exit 1; }
git fetch origin
[[ "$(git rev-parse HEAD)" == "$(git rev-parse '@{upstream}')" ]] || { echo "FuzzBench HEAD does not match upstream" >&2; exit 1; }
[[ "$(df -BG --output=avail /data | awk 'NR==2 {gsub(/G/,"",$1);print $1}')" -ge 50 ]] || { echo "/data free < 50GB" >&2; exit 1; }

MARKER="${BATCH}/manifests/latest_quality_gate_root.txt"
case "$STAGE" in
  curl)
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    QROOT="${BATCH}/results/quality_gate_${TS}"
    mkdir -p "$QROOT"
    printf '%s\n' "$QROOT" > "$MARKER"
    BENCHMARKS=(curl_curl_fuzzer_http)
    RUNNERS_CPUS=10
    MEASURERS_CPUS=10
    ;;
  core-rest)
    [[ -f "$MARKER" ]] || { echo "missing curl quality-gate root" >&2; exit 1; }
    QROOT="$(<"$MARKER")"
    python3 - "$QROOT/quality_gate_decision.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
if d.get('curl_status') != 'PASS':
    raise SystemExit('core-rest requires curl_status=PASS')
PY
    BENCHMARKS=("${CORE_REST[@]}")
    RUNNERS_CPUS=40
    MEASURERS_CPUS=24
    ;;
  fallback-five)
    [[ -f "$MARKER" ]] || { echo "missing curl quality-gate root" >&2; exit 1; }
    QROOT="$(<"$MARKER")"
    python3 - "$QROOT/quality_gate_decision.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
if d.get('curl_status') != 'FAIL':
    raise SystemExit('fallback-five requires preserved curl_status=FAIL')
PY
    BENCHMARKS=("${FALLBACK_FIVE[@]}")
    RUNNERS_CPUS=50
    MEASURERS_CPUS=24
    ;;
esac

RUN_DIR="${QROOT}/${STAGE}"
[[ ! -e "$RUN_DIR" ]] || { echo "refusing to overwrite existing quality stage: $RUN_DIR" >&2; exit 1; }
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/reports"
CONFIG_RUN="$RUN_DIR/config.yaml"
cp "$CONFIG_TEMPLATE" "$CONFIG_RUN"
sed -i \
  -e "s#experiment_filestore: .*#experiment_filestore: ${RUN_DIR}/experiment-data#" \
  -e "s#report_filestore: .*#report_filestore: ${RUN_DIR}/reports#" \
  "$CONFIG_RUN"

EXP="baq$(echo "$STAGE" | tr -d '-')-$(date -u +%m%d%H%M%S)"
(( ${#EXP} <= 30 )) || { echo "experiment name too long: $EXP" >&2; exit 1; }
{
  echo "stage=$STAGE"
  echo "quality_root=$QROOT"
  echo "experiment=$EXP"
  echo "fuzzbench_commit=$(git rev-parse HEAD)"
  echo "aflplusplus_commit=8224da1dce693d0a7de8d21cd9108c4e0e3a5b54"
  echo "runners_cpus=$RUNNERS_CPUS"
  echo "measurers_cpus=$MEASURERS_CPUS"
  printf 'benchmarks=%s\n' "${BENCHMARKS[*]}"
  printf 'fuzzers=%s\n' "${FUZZERS[*]}"
  date -Is
  df -h / /data
} > "$RUN_DIR/stage_provenance.txt"

PYTHONPATH=. .venv/bin/python3 experiment/run_experiment.py \
  --experiment-config "$CONFIG_RUN" \
  --experiment-name "$EXP" \
  --description "AdaRare Batch A one-hour quality gate stage ${STAGE}; strict build/hash gate already passed" \
  --benchmarks "${BENCHMARKS[@]}" \
  --fuzzers "${FUZZERS[@]}" \
  --concurrent-builds 2 \
  --runners-cpus "$RUNNERS_CPUS" \
  --measurers-cpus "$MEASURERS_CPUS" \
  2>&1 | tee "$RUN_DIR/logs/run_experiment.log"

python3 "${BATCH}/scripts/audit_batch_a_quality_gate.py" --root "$QROOT"
