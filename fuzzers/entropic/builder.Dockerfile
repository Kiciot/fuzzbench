# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# ----------------------------
# Proxy
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

# ----------------------------
# Pin libFuzzer source to a recent llvm-project commit
# ----------------------------
ARG LLVM_COMMIT="9d18e92ee78c4171477d5a868bd8ad3c1dbf07a1"

# ----------------------------
# Minimal deps + git robustness
# ----------------------------
RUN set -eux; \
  apt-get update; \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
  ; \
  rm -rf /var/lib/apt/lists/*; \
  \
  git config --global http.version HTTP/1.1; \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY:-$HTTP_PROXY}"; \
  fi; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  git config --global core.compression 0

# ----------------------------
# Build libFuzzer.a from compiler-rt/lib/fuzzer
# Also overwrite /lib/libFuzzingEngine.a to avoid mixed-engine link issues.
# ----------------------------
RUN set -eux; \
  rm -rf /llvm-project; \
  mkdir -p /llvm-project; \
  cd /llvm-project; \
  git init; \
  git remote add origin https://github.com/llvm/llvm-project.git; \
  git -c http.version=HTTP/1.1 fetch --depth 1 origin "${LLVM_COMMIT}"; \
  git checkout -q FETCH_HEAD; \
  \
  cd compiler-rt/lib/fuzzer; \
  rm -f ./*.o /usr/lib/libFuzzer.a /lib/libFuzzingEngine.a; \
  \
  for f in *.cpp; do \
    clang++ -stdlib=libc++ -fPIC -O2 -std=c++17 "$f" -c & \
  done; \
  wait; \
  \
  ar rcs /usr/lib/libFuzzer.a ./*.o; \
  ranlib /usr/lib/libFuzzer.a; \
  \
  nm -C /usr/lib/libFuzzer.a | awk 'index($0,"fuzzer::Fuzzer::Fuzzer"){found=1} END{exit !found}'; \
  \
  cp -f /usr/lib/libFuzzer.a /lib/libFuzzingEngine.a; \
  ranlib /lib/libFuzzingEngine.a