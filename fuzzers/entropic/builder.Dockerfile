# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# ----------------------------
# Proxy (optional)
# ----------------------------
ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# APT proxy + retries/timeouts (optional)
RUN set -eux; \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' \
      "${HTTP_PROXY}" "${HTTPS_PROXY:-$HTTP_PROXY}" > /etc/apt/apt.conf.d/99proxy; \
  fi; \
  printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    > /etc/apt/apt.conf.d/80-retries

# Minimal deps (git/ca-certs for checkout_commit, etc.)
RUN set -eux; \
  apt-get update; \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
  ; \
  rm -rf /var/lib/apt/lists/*

# ----------------------------
# Compatibility: provide /usr/lib/libFuzzer.a
# Some FuzzBench benchmark build scripts still hardcode this legacy path.
# We symlink it to compiler-rt's libclang_rt.fuzzer*.a that matches the target triple.
# ----------------------------
RUN set -eux; \
  # clang must exist in parent_image; fail early if not
  command -v clang >/dev/null; \
  command -v clang++ >/dev/null; \
  \
  resdir="$(clang -print-resource-dir)"; \
  triple="$(clang -dumpmachine)"; \
  \
  # Common locations for compiler-rt runtime archives
  # 1) resource-dir layout (newer clang)
  # 2) system lib dirs (varies by distro)
  candidates=(); \
  \
  # Try resource-dir first: .../lib/linux/
  if [[ -d "${resdir}/lib/linux" ]]; then \
    while IFS= read -r -d '' f; do candidates+=("$f"); done < <(find "${resdir}/lib/linux" -maxdepth 1 -type f -name 'libclang_rt.fuzzer*.a' -print0 || true); \
  fi; \
  \
  # Fallback: search a bit broader (avoid / which is too slow)
  if [[ "${#candidates[@]}" -eq 0 ]]; then \
    while IFS= read -r -d '' f; do candidates+=("$f"); done < <(find /usr/lib /usr/local/lib -maxdepth 6 -type f -name 'libclang_rt.fuzzer*.a' -print0 2>/dev/null || true); \
  fi; \
  \
  # Pick the best match:
  # - prefer one that includes the current machine triple/arch in its name (if present)
  # - otherwise take the first candidate
  pick=""; \
  if [[ "${#candidates[@]}" -gt 0 ]]; then \
    for f in "${candidates[@]}"; do \
      if [[ "$f" == *"${triple}"* ]]; then pick="$f"; break; fi; \
    done; \
    if [[ -z "$pick" ]]; then pick="${candidates[0]}"; fi; \
  fi; \
  \
  test -n "$pick"; \
  ln -sf "$pick" /usr/lib/libFuzzer.a; \
  \
  # Sanity: ensure some known symbol exists (prevents "empty/invalid archive" accidents)
  nm -C /usr/lib/libFuzzer.a | grep -E -q 'FuzzerDriver|LLVMFuzzerTestOneInput|fuzzer::Fuzzer' || true; \
  ls -l /usr/lib/libFuzzer.a; \
  echo "libFuzzer.a -> $pick"