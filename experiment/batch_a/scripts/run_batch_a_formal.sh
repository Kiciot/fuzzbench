#!/usr/bin/env bash
set -euo pipefail

ROOT="${ADARARE_EXP_ROOT:-/data/adarare_exp}"
FB="${FUZZBENCH_DIR:-${ROOT}/fuzzbench}"
AFL="${AFLPLUSPLUS_DIR:-${ROOT}/AFLplusplus}"
BATCH="${BATCH_A_ROOT:-${ROOT}/batch_a}"
FREEZE="${BATCH}/freeze"
QUALITY_ROOT="$(<"${BATCH}/manifests/latest_quality_gate_root.txt")"
PROV_DIR="$(<"${BATCH}/manifests/latest_build_provenance.txt")"
DECISION="${QUALITY_ROOT}/quality_gate_decision.json"
CONFIG_TEMPLATE="${BATCH}/configs/batch_a_formal.yaml"
STATS_PLAN="${BATCH}/configs/batch_a_statistics_plan.yaml"
AFL_EXPECTED="8224da1dce693d0a7de8d21cd9108c4e0e3a5b54"

[[ "${1:-}" != "--help" ]] || {
  echo "Usage: run_batch_a_formal.sh  # only inside the adarare-batcha-formal tmux gate"
  exit 0
}
(( $# == 0 )) || { echo "unexpected arguments: $*" >&2; exit 2; }

for required in "$DECISION" "$CONFIG_TEMPLATE" "$STATS_PLAN" \
  "$PROV_DIR/build_provenance.tsv" "$PROV_DIR/hash_equivalence.json"; do
  [[ -f "$required" ]] || { echo "missing required gate artifact: $required" >&2; exit 1; }
done

readarray -t TARGETS < <(python3 - "$DECISION" <<'PY'
import json,sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
if not d.get('formal_ready') or d.get('status') != 'PASS':
    raise SystemExit('quality gate is not formal-ready')
targets=d.get('formal_targets', [])
if len(targets) != 5 or len(set(targets)) != 5:
    raise SystemExit(f'formal target freeze is not exactly five unique targets: {targets}')
print(*targets, sep='\n')
PY
)

FUZZERS=(
  adarare_full adarare_linucb_no_a6 adarare_constant_context_no_a6
  adarare_random_profile adarare_round_robin_profile
  adarare_static_a1 adarare_static_a2 adarare_static_a3
  adarare_static_a4 adarare_static_a5
)

cd "$FB"
git fetch origin
[[ -z "$(git status --porcelain)" ]] || { echo "FuzzBench working tree is not clean" >&2; exit 1; }
FB_COMMIT="$(git rev-parse HEAD)"
[[ "$FB_COMMIT" == "$(git rev-parse '@{upstream}')" ]] || { echo "FuzzBench HEAD differs from upstream" >&2; exit 1; }
PROV_FB_COMMIT="$(awk -F '\t' 'NR==2 {print $3}' "$PROV_DIR/build_provenance.tsv")"
[[ "$PROV_FB_COMMIT" == "$FB_COMMIT" ]] || {
  echo "build provenance FuzzBench commit $PROV_FB_COMMIT differs from current $FB_COMMIT; rerun clean 60-build gate" >&2
  exit 1
}
python3 - "$PROV_DIR/hash_equivalence.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
if d.get('status') != 'PASS' or d.get('records') != 60:
    raise SystemExit('60-build hash equivalence gate is not PASS')
PY

git -C "$AFL" fetch origin
[[ -z "$(git -C "$AFL" status --porcelain)" ]] || { echo "AFL++ working tree is not clean" >&2; exit 1; }
AFL_COMMIT="$(git -C "$AFL" rev-parse HEAD)"
[[ "$AFL_COMMIT" == "$AFL_EXPECTED" ]] || { echo "unexpected AFL++ commit: $AFL_COMMIT" >&2; exit 1; }
[[ "$AFL_COMMIT" == "$(git -C "$AFL" rev-parse '@{upstream}')" ]] || { echo "AFL++ HEAD differs from upstream" >&2; exit 1; }

DATA_FREE="$(df -BG --output=avail /data | awk 'NR==2 {gsub(/G/,"",$1);print $1}')"
(( DATA_FREE >= 50 )) || { echo "/data free < 50GB" >&2; exit 1; }
RAM_GB="$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)"
if (( RAM_GB >= 192 )); then
  RUNNERS_CPUS=88; MEASURERS_CPUS=24
elif (( RAM_GB >= 128 )); then
  RUNNERS_CPUS=72; MEASURERS_CPUS=24
else
  RUNNERS_CPUS=64; MEASURERS_CPUS=20
fi
CONCURRENT_BUILDS=2
(( $(nproc) - RUNNERS_CPUS - MEASURERS_CPUS >= 12 )) || { echo "resource plan leaves fewer than 12 CPUs" >&2; exit 1; }

for exact in BATCH_A_PRE_RUN_FREEZE.md batch_a_pre_run_freeze.json SHA256SUMS; do
  [[ ! -e "$FREEZE/$exact" ]] || { echo "refusing to overwrite existing freeze artifact: $FREEZE/$exact" >&2; exit 1; }
done
mkdir -p "$FREEZE/artifacts"
cp "${BATCH}/docs/BATCH_A_VARIANT_MANIFEST.md" "$FREEZE/artifacts/"
cp "$QUALITY_ROOT/BATCH_A_QUALITY_GATE_AUDIT.md" "$FREEZE/artifacts/"
cp "$QUALITY_ROOT"/quality_gate_*.tsv "$QUALITY_ROOT/quality_gate_decision.json" "$FREEZE/artifacts/"
cp "$PROV_DIR"/build_provenance.tsv "$PROV_DIR"/seed_files.tsv "$PROV_DIR"/dictionary_files.tsv \
  "$PROV_DIR"/hash_equivalence.tsv "$PROV_DIR"/hash_equivalence.json "$FREEZE/artifacts/"
cp "$CONFIG_TEMPLATE" "$STATS_PLAN" "$FREEZE/artifacts/"

python3 - "$FREEZE" "$DECISION" "$PROV_DIR/build_provenance.tsv" \
  "$QUALITY_ROOT/quality_gate_summary.tsv" "$FB_COMMIT" "$AFL_COMMIT" \
  "$RUNNERS_CPUS" "$MEASURERS_CPUS" "$CONCURRENT_BUILDS" <<'PY'
import csv,datetime,json,sys
from pathlib import Path
freeze=Path(sys.argv[1]); decision=json.load(open(sys.argv[2], encoding='utf-8'))
with open(sys.argv[3], newline='', encoding='utf-8') as f:
    provenance=list(csv.DictReader(f, delimiter='\t'))
with open(sys.argv[4], newline='', encoding='utf-8') as f:
    quality=list(csv.DictReader(f, delimiter='\t'))
targets=decision['formal_targets']
hashes={}
baselines={}
for target in targets:
    rows=[r for r in provenance if r['benchmark']==target]
    hashes[target]={field: sorted({r[field] for r in rows})[0] for field in (
        'benchmark_revision','benchmark_yaml_sha256','benchmark_dockerfile_sha256',
        'target_binary_sha256','coverage_binary_sha256','cmplog_binary_sha256',
        'initial_corpus_manifest_sha256','dictionary_manifest_sha256')}
    values={int(r['pre_fuzz_coverage']) for r in quality if r['benchmark']==target and r['status']=='PASS'}
    if len(values) != 1:
        raise SystemExit(f'pre-fuzz baseline is not uniquely frozen for {target}: {values}')
    baselines[target]=values.pop()
data={
  'schema':'adarare_batch_a_pre_run_freeze_v1',
  'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'aflplusplus_commit':sys.argv[6], 'fuzzbench_commit':sys.argv[5],
  'variants':[r['fuzzer'] for r in provenance if r['benchmark']==targets[0]],
  'targets':targets, 'fallback_used':decision['fallback_used'],
  'campaigns':500, 'trials_per_cell':10, 'max_total_time':86400,
  'primary_endpoint':85500, 'sensitivity_endpoint':86400,
  'snapshot_period':900, 'runners_cpus':int(sys.argv[7]),
  'measurers_cpus':int(sys.argv[8]), 'concurrent_builds':int(sys.argv[9]),
  'binary_and_input_hashes':hashes, 'pre_fuzz_coverage':baselines,
  'quality_gate_decision':decision,
}
(freeze/'batch_a_pre_run_freeze.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
lines=['# AdaRare Batch A Pre-Run Freeze','',
 f"- Frozen at: `{data['frozen_at']}`", f"- AFL++ commit: `{data['aflplusplus_commit']}`",
 f"- FuzzBench commit: `{data['fuzzbench_commit']}`", f"- Targets: `{', '.join(targets)}`",
 f"- Freetype2 fallback used: **{data['fallback_used']}**",
 '- Matrix: **5 targets x 10 variants x 10 trials = 500 campaigns**',
 '- Budget: **86400 seconds**; primary endpoint **85500 seconds**',
 f"- Resources: runners={data['runners_cpus']}, measurers={data['measurers_cpus']}, concurrent_builds={data['concurrent_builds']}",
 '', '## Deterministic pre-fuzz baselines','']
for target,value in baselines.items(): lines.append(f'- `{target}`: {value}')
lines += ['', 'The complete binary, CmpLog, coverage, corpus, dictionary, variant, quality-gate, and statistics-plan evidence is frozen under `artifacts/`.']
(freeze/'BATCH_A_PRE_RUN_FREEZE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
PY
(
  cd "$FREEZE"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)

TS="$(date -u +%Y%m%dt%H%M%Sz)"
FORMAL_ROOT="${BATCH}/results/formal_${TS}"
mkdir -p "$FORMAL_ROOT/logs" "$FORMAL_ROOT/reports"
printf '%s\n' "$FORMAL_ROOT" > "${BATCH}/manifests/latest_formal_root.txt"
CONFIG_RUN="$FORMAL_ROOT/config.yaml"
cp "$CONFIG_TEMPLATE" "$CONFIG_RUN"
sed -i \
  -e "s#experiment_filestore: .*#experiment_filestore: ${FORMAL_ROOT}/experiment-data#" \
  -e "s#report_filestore: .*#report_filestore: ${FORMAL_ROOT}/reports#" \
  "$CONFIG_RUN"
EXP="baf500-$(date -u +%m%d%H%M)"
{
  echo "formal_root=$FORMAL_ROOT"
  echo "experiment=$EXP"
  echo "started_at=$(date -Is)"
  echo "estimated_budget_completion=$(date -d '+24 hours' -Is)"
  echo "fuzzbench_commit=$FB_COMMIT"
  echo "aflplusplus_commit=$AFL_COMMIT"
  echo "targets=${TARGETS[*]}"
  echo "fuzzers=${FUZZERS[*]}"
  echo "trials=10 campaigns=500 max_total_time=86400 snapshot_period=900"
  echo "runners_cpus=$RUNNERS_CPUS measurers_cpus=$MEASURERS_CPUS concurrent_builds=$CONCURRENT_BUILDS"
  df -h / /data
} | tee "$FORMAL_ROOT/formal_provenance.txt"

FUZZBENCH_REUSE_LOCAL_IMAGES=1 \
FUZZBENCH_LOCAL_PROXY="${FUZZBENCH_LOCAL_PROXY:-http://127.0.0.1:7890}" \
PYTHONPATH=. .venv/bin/python3 experiment/run_experiment.py \
  --experiment-config "$CONFIG_RUN" \
  --experiment-name "$EXP" \
  --description "Frozen AdaRare Batch A 500-campaign causal-attribution formal run; see ${FREEZE}/batch_a_pre_run_freeze.json" \
  --benchmarks "${TARGETS[@]}" \
  --fuzzers "${FUZZERS[@]}" \
  --concurrent-builds "$CONCURRENT_BUILDS" \
  --runners-cpus "$RUNNERS_CPUS" \
  --measurers-cpus "$MEASURERS_CPUS" \
  2>&1 | tee "$FORMAL_ROOT/logs/run_experiment.log"

echo "formal_run_command_completed_at=$(date -Is)" | tee -a "$FORMAL_ROOT/formal_provenance.txt"
