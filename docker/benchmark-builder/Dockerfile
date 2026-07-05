# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

ARG parent_image

# Using multi-stage build to copy latest Python 3.
FROM gcr.io/fuzzbench/base-image AS base-image

FROM $parent_image

ARG fuzzer
ARG benchmark
ARG debug_builder

# -----------------------------
# 1) Build-time identity
# -----------------------------
ENV FUZZER=$fuzzer \
    BENCHMARK=$benchmark \
    DEBUG_BUILDER=$debug_builder \
    GIT_TERMINAL_PROMPT=0

# -----------------------------
# 2) APT robustness: mirror + retries + timeouts
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
        -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
        /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# 3) Base deps (NO apt upgrade)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        git \
        xz-utils \
        zlib1g-dev \
        libssl-dev \
        libffi-dev \
      && break; \
      echo "apt-get failed ($i/5), retrying..." >&2; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# 4) Git robustness
# -----------------------------
RUN set -eux; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global http.version HTTP/1.1

# -----------------------------
# 5) Helper: robust download (curl first; fallback wget; curl flags are "old-curl safe")
#    Usage: _dl_retry <url1> [url2] [url3] <out>
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
'#!/bin/sh' \
'set -eu' \
'url1="${1:-}"' \
'url2="${2:-}"' \
'url3="${3:-}"' \
'out="${4:-}"' \
'[ -n "$url1" ] && [ -n "$out" ] || { echo "usage: _dl_retry <url1> [url2] [url3] <out>" >&2; exit 2; }' \
'try_one() {' \
'  url="$1"' \
'  i=1' \
'  while [ "$i" -le 8 ]; do' \
'    rm -f "$out"' \
'    if command -v curl >/dev/null 2>&1; then' \
'      if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 15 --max-time 300 -o "$out" "$url"; then return 0; fi' \
'      # Some envs need -k; enable only when SSL handshake fails repeatedly by uncommenting next line:' \
'      # if curl -kfsSL --retry 3 --retry-delay 2 --connect-timeout 15 --max-time 300 -o "$out" "$url"; then return 0; fi' \
'    fi' \
'    if command -v wget >/dev/null 2>&1; then' \
'      if wget -O "$out" --tries=3 --timeout=60 "$url"; then return 0; fi' \
'      # if wget --no-check-certificate -O "$out" --tries=3 --timeout=60 "$url"; then return 0; fi' \
'    fi' \
'    echo "download failed ($i/8): $url" >&2' \
'    i=$((i+1))' \
'    sleep 5' \
'  done' \
'  return 1' \
'}' \
'for url in "$url1" "$url2" "$url3"; do' \
'  [ -n "$url" ] || continue' \
'  if try_one "$url"; then exit 0; fi' \
'done' \
'echo "download permanently failed (all mirrors): $url1" >&2' \
'exit 1' \
      > /usr/local/bin/_dl_retry; \
    chmod +x /usr/local/bin/_dl_retry

# -----------------------------
# 6) Remove old python3.8 artifacts from parent image (ignore if missing)
# -----------------------------
RUN set -eux; \
    rm -rf \
      /usr/local/bin/python3.8* \
      /usr/local/bin/pip3 \
      /usr/local/lib/python3.8 \
      /usr/local/include/python3.8 \
      /usr/local/lib/python3.8/site-packages \
      || true

# Copy latest python3 from base-image into local.
COPY --from=base-image /usr/local/bin/python3* /usr/local/bin/
COPY --from=base-image /usr/local/bin/pip3* /usr/local/bin/
COPY --from=base-image /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=base-image /usr/local/include/python3.10 /usr/local/include/python3.10
COPY --from=base-image /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy the entire fuzzers directory tree to allow for module dependencies.
COPY fuzzers $SRC/fuzzers

# Disable LeakSanitizer since ptrace is unavailable in Google Cloud build
ENV ASAN_OPTIONS="detect_leaks=0"

COPY benchmarks/$benchmark/benchmark.yaml /

RUN mkdir -p /opt/fuzzbench/
COPY docker/benchmark-builder/checkout_commit.py /opt/fuzzbench/

# Checkout pinned commit
RUN set -eux; \
    CHECKOUT_COMMIT="$(tr -d ' ' < /benchmark.yaml | grep '^commit:' | cut -d ':' -f2)"; \
    python3 -u /opt/fuzzbench/checkout_commit.py "$CHECKOUT_COMMIT" "$SRC"

COPY docker/benchmark-builder/fuzzer_build /usr/bin/fuzzer_build

# Build target
RUN echo "Run fuzzer_build to build the target" && \
    if [ -z "$debug_builder" ] ; then fuzzer_build; fi