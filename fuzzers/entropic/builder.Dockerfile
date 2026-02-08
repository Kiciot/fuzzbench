# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

SHELL ["/bin/bash", "-exo", "pipefail", "-c"]

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

# APT proxy + retries/timeouts (optional but helps behind proxy)
RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' \
      "${HTTP_PROXY}" "${HTTPS_PROXY:-$HTTP_PROXY}" > /etc/apt/apt.conf.d/99proxy; \
  fi && \
  printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    > /etc/apt/apt.conf.d/80-retries

# Minimal deps
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Compatibility: provide /usr/lib/libFuzzer.a
# Some FuzzBench benchmarks still hardcode this legacy path.
# ----------------------------
RUN set -eux; \
  # Preferred: use clang resource dir (compiler-rt fuzzer runtime)
  resdir="$(clang -print-resource-dir)"; \
  cand="${resdir}/lib/linux/libclang_rt.fuzzer-x86_64.a"; \
  if [[ -f "${cand}" ]]; then \
    ln -sf "${cand}" /usr/lib/libFuzzer.a; \
  else \
    # Fallback search (covers different distros/clang layouts)
    cand="$(find /usr/lib /usr/local / -maxdepth 6 \
      -type f \( -name 'libclang_rt.fuzzer*.a' -o -name 'libFuzzer.a' \) \
      2>/dev/null | head -n1 || true)"; \
    test -n "${cand}"; \
    ln -sf "${cand}" /usr/lib/libFuzzer.a; \
  fi; \
  ls -l /usr/lib/libFuzzer.a