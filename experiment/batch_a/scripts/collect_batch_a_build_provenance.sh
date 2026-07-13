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
  echo "usage: collect_batch_a_build_provenance.sh [build_matrix_result_dir]" >&2
  exit 2
}

OUT="${BUILD_DIR}/provenance"
PROV="${OUT}/build_provenance.tsv"
SEEDS="${OUT}/seed_files.tsv"
DICTS="${OUT}/dictionary_files.tsv"
mkdir -p "$OUT"

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

printf 'benchmark\tfuzzer\tfuzzbench_commit\taflplusplus_commit\tbenchmark_revision\tbenchmark_yaml_sha256\tbenchmark_dockerfile_sha256\tbuilder_image_id\tbuilder_image_digest\trunner_image_id\trunner_image_digest\ttarget_binary_sha256\tcoverage_binary_sha256\tcmplog_binary_sha256\tinitial_corpus_manifest_sha256\tseed_file_count\tdictionary_manifest_sha256\tdictionary_file_count\tcompiler_version\tllvm_version\tsanitizer\tvariant_env\tbuilder_dockerfile_sha256\tfuzzer_py_sha256\tnormalized_runner_sha256\n' > "$PROV"
printf 'benchmark\tfuzzer\tseed_path\tsha256\n' > "$SEEDS"
printf 'benchmark\tfuzzer\tdictionary_path\tsha256\n' > "$DICTS"

clean() { tr '\t\r\n' '   ' | sed -E 's/ +/ /g; s/^ //; s/ $//'; }
image_id() { docker image inspect --format '{{.Id}}' "$1"; }
image_digest() {
  local value
  value="$(docker image inspect --format '{{join .RepoDigests ","}}' "$1")"
  [[ -n "$value" ]] && printf '%s' "$value" || printf 'LOCAL_NO_REPODIGEST'
}
inside() { docker run --rm --entrypoint /bin/bash "$1" -lc "$2"; }
inside_hash() {
  inside "$1" "test -f '$2' && sha256sum '$2' | awk '{print \$1}'"
}
inside_manifest() {
  local image="$1" kind="$2"
  case "$kind" in
    seeds)
      inside "$image" "if test -d /out/seeds; then find /out/seeds -type f -printf '%P\\0' | sort -z | while IFS= read -r -d '' p; do sha256sum \"/out/seeds/\$p\" | awk -v p=\"\$p\" '{print \$1 \"  \" p}'; done; fi"
      ;;
    dicts)
      inside "$image" "find /out -type f -name '*.dict' -printf '%P\\0' | sort -z | while IFS= read -r -d '' p; do sha256sum \"/out/\$p\" | awk -v p=\"\$p\" '{print \$1 \"  \" p}'; done"
      ;;
    *) return 2 ;;
  esac
}
manifest_sha() { sha256sum "$1" | awk '{print $1}'; }

cd "$FB"
FB_COMMIT="$(git rev-parse HEAD)"
AFL_COMMIT="$(sed -n 's/^ARG AFLPLUSPLUS_COMMIT=//p' fuzzers/adarare_full/builder.Dockerfile | head -1)"
[[ "$AFL_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid AFL++ pin: $AFL_COMMIT" >&2; exit 1; }

for benchmark in "${BENCHMARKS[@]}"; do
  yaml="benchmarks/${benchmark}/benchmark.yaml"
  dockerfile="benchmarks/${benchmark}/Dockerfile"
  target="$(sed -n 's/^fuzz_target:[[:space:]]*//p' "$yaml" | head -1)"
  revision="$(sed -n 's/^commit:[[:space:]]*//p' "$yaml" | head -1)"
  [[ -n "$revision" ]] || revision="EMPTY_COMMIT_FIELD_AT_${FB_COMMIT}"
  yaml_sha="$(sha256sum "$yaml" | awk '{print $1}')"
  dockerfile_sha="$(sha256sum "$dockerfile" | awk '{print $1}')"
  coverage_image="gcr.io/fuzzbench/builders/coverage/${benchmark}"
  docker image inspect "$coverage_image" >/dev/null
  coverage_sha="$(inside_hash "$coverage_image" "/out/${target}")"
  [[ "$coverage_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "missing coverage binary for $benchmark" >&2; exit 1; }

  for fuzzer in "${FUZZERS[@]}"; do
    builder_image="gcr.io/fuzzbench/builders/${fuzzer}/${benchmark}"
    runner_image="gcr.io/fuzzbench/runners/${fuzzer}/${benchmark}"
    docker image inspect "$builder_image" "$runner_image" >/dev/null

    target_sha="$(inside_hash "$builder_image" "/out/${target}")"
    cmplog_sha="$(inside_hash "$builder_image" "/out/cmplog/${target}")"
    [[ "$target_sha" =~ ^[0-9a-f]{64}$ && "$cmplog_sha" =~ ^[0-9a-f]{64}$ ]] || {
      echo "missing target or CmpLog binary for $benchmark/$fuzzer" >&2
      exit 1
    }

    seed_tmp="$(mktemp)"
    dict_tmp="$(mktemp)"
    inside_manifest "$runner_image" seeds > "$seed_tmp"
    inside_manifest "$runner_image" dicts > "$dict_tmp"
    seed_manifest_sha="$(manifest_sha "$seed_tmp")"
    dict_manifest_sha="$(manifest_sha "$dict_tmp")"
    seed_count="$(wc -l < "$seed_tmp" | tr -d ' ')"
    dict_count="$(wc -l < "$dict_tmp" | tr -d ' ')"
    while read -r sha path; do
      [[ -n "${sha:-}" ]] || continue
      printf '%s\t%s\t%s\t%s\n' "$benchmark" "$fuzzer" "$path" "$sha" >> "$SEEDS"
    done < "$seed_tmp"
    while read -r sha path; do
      [[ -n "${sha:-}" ]] || continue
      printf '%s\t%s\t%s\t%s\n' "$benchmark" "$fuzzer" "$path" "$sha" >> "$DICTS"
    done < "$dict_tmp"

    compiler="$(inside "$builder_image" "clang --version 2>/dev/null | head -1 || cc --version 2>/dev/null | head -1 || true" | clean)"
    llvm="$(inside "$builder_image" "llvm-config --version 2>/dev/null || clang --version 2>/dev/null | head -1 || true" | clean)"
    sanitizer="$(docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$builder_image" | sed -n 's/^SANITIZER=//p' | head -1 | clean)"
    [[ -n "$sanitizer" ]] || sanitizer="UNSET_IMAGE_ENV"
    variant_env="$(docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$runner_image" | grep '^AFL_ADARARE_' | sort | paste -sd ';' - | clean)"
    builder_docker_sha="$(sha256sum "fuzzers/${fuzzer}/builder.Dockerfile" | awk '{print $1}')"
    fuzzer_py_sha="$(sha256sum "fuzzers/${fuzzer}/fuzzer.py" | awk '{print $1}')"
    normalized_runner_sha="$(grep -v '^ENV AFL_ADARARE_' "fuzzers/${fuzzer}/runner.Dockerfile" | sha256sum | awk '{print $1}')"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$benchmark" "$fuzzer" "$FB_COMMIT" "$AFL_COMMIT" "$revision" "$yaml_sha" "$dockerfile_sha" \
      "$(image_id "$builder_image")" "$(image_digest "$builder_image")" \
      "$(image_id "$runner_image")" "$(image_digest "$runner_image")" \
      "$target_sha" "$coverage_sha" "$cmplog_sha" "$seed_manifest_sha" "$seed_count" \
      "$dict_manifest_sha" "$dict_count" "$compiler" "$llvm" "$sanitizer" "$variant_env" \
      "$builder_docker_sha" "$fuzzer_py_sha" "$normalized_runner_sha" >> "$PROV"
    rm -f "$seed_tmp" "$dict_tmp"
    echo "collected $benchmark/$fuzzer"
  done
done

records="$(awk 'END {print NR-1}' "$PROV")"
[[ "$records" == 60 ]] || { echo "expected 60 provenance records, got $records" >&2; exit 1; }
sha256sum "$PROV" "$SEEDS" "$DICTS" > "${OUT}/SHA256SUMS"
printf '%s\n' "$OUT" > "${BATCH}/manifests/latest_build_provenance.txt"
echo "provenance=$PROV records=$records"
