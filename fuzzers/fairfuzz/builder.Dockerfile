# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

# Fail fast, pipefail. Use bash if present in typical OSS-Fuzz base-builder images.
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# ----------------------------
# Proxy (keeps your logic)
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

# APT proxy + retries/timeouts
RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' \
      "${HTTP_PROXY}" "${HTTPS_PROXY:-$HTTP_PROXY}" > /etc/apt/apt.conf.d/99proxy; \
  fi && \
  printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    > /etc/apt/apt.conf.d/80-retries

# ----------------------------
# Deps (do NOT install clang/llvm to avoid conflicts with parent)
# ----------------------------
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      make \
      binutils \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Build AFL-RB (FairFuzz fork)
# ----------------------------
ARG AFL_RB_COMMIT="e529c1f1b3666ad94e4d6e7ef24ea648aff39ae2"

RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    git config --global http.proxy "${HTTP_PROXY}"; \
  fi && \
  git clone https://github.com/carolemieux/afl-rb.git /afl && \
  cd /afl && \
  git checkout "${AFL_RB_COMMIT}" && \
  \
  # Use compiler from parent image. Avoid AFL_NO_X86 unless you really need it.
  CC=clang make clean all

# ----------------------------
# Build AFL Driver static lib (afl-llvm-rt + afl_driver)
# Place it under /afl for predictable linking.
# ----------------------------
WORKDIR /afl
ARG LLVM_COMMIT="5feb80e748924606531ba28c97fe65145c65372e"

RUN \
  url="https://raw.githubusercontent.com/llvm/llvm-project/${LLVM_COMMIT}/compiler-rt/lib/fuzzer/afl/afl_driver.cpp"; \
  wget -t 5 -T 30 -O afl_driver.cpp "${url}" && \
  \
  # Build AFL LLVM runtime from afl-rb source tree
  clang -Wno-pointer-sign -c llvm_mode/afl-llvm-rt.o.c -I. -o afl-llvm-rt.o && \
  \
  # Build driver. Do not force libc++ unless your whole toolchain uses it.
  clang++ -std=c++11 -O2 -c afl_driver.cpp -o afl_driver.o && \
  \
  # Archive as a static library with index.
  ar rcs /afl/libAFLDriver.a afl-llvm-rt.o afl_driver.o

# ----------------------------
# FuzzBench convention
# ----------------------------
WORKDIR /src