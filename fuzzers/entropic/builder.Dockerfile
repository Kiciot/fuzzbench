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

# Minimal deps (+file/binutils for sanity checks)
RUN set -eux; \
  apt-get update; \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    file \
    binutils \
  ; \
  rm -rf /var/lib/apt/lists/*

# ----------------------------
# Compatibility: provide /usr/lib/libFuzzer.a
# Some FuzzBench benchmark build scripts still hardcode this legacy path.
# We symlink it to compiler-rt's libclang_rt.fuzzer-<arch>.a with the correct arch,
# avoiding accidental i386 archives on amd64 builds.
# ----------------------------
RUN set -eux; \
  command -v clang >/dev/null; \
  command -v clang++ >/dev/null; \
  \
  arch="$(uname -m)"; \
  case "${arch}" in \
    x86_64|amd64) rt_arch="x86_64" ;; \
    aarch64|arm64) rt_arch="aarch64" ;; \
    *) echo "Unsupported arch: ${arch}" >&2; exit 1 ;; \
  esac; \
  \
  resdir="$(clang -print-resource-dir)"; \
  \
  cand="${resdir}/lib/linux/libclang_rt.fuzzer-${rt_arch}.a"; \
  if [[ ! -f "${cand}" ]]; then \
    cand="$(find /usr/lib /usr/local/lib -maxdepth 8 -type f \
      -name "libclang_rt.fuzzer-${rt_arch}.a" -print 2>/dev/null | head -n1 || true)"; \
  fi; \
  if [[ -z "${cand}" || ! -f "${cand}" ]]; then \
    echo "Cannot find libclang_rt.fuzzer-${rt_arch}.a" >&2; \
    echo "clang resource dir: ${resdir}" >&2; \
    ls -al "${resdir}/lib/linux" || true; \
    find /usr/lib /usr/local/lib -maxdepth 4 -type f -name 'libclang_rt.fuzzer*.a' -print 2>/dev/null || true; \
    exit 1; \
  fi; \
  \
  rm -f /usr/lib/libFuzzer.a; \
  ln -s "${cand}" /usr/lib/libFuzzer.a; \
  echo "libFuzzer.a -> $(readlink -f /usr/lib/libFuzzer.a)"; \
  file /usr/lib/libFuzzer.a; \
  \
  # Sanity (soft): symbol presence check; don't fail build if toolchain strips it
  nm -A /usr/lib/libFuzzer.a 2>/dev/null | grep -E -q 'FuzzerDriver|LLVMFuzzerTestOneInput' || true; \
  ls -l /usr/lib/libFuzzer.a