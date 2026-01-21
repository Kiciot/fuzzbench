# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---------
# APT: retries + basic deps
# ---------
RUN set -eux; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  for i in 1 2 3 4 5; do \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      curl \
      make \
      autoconf \
      automake \
      libtool \
      zlib1g-dev \
    && break; \
    echo "apt-get failed, retry $i/5" >&2; \
    sleep 10; \
    apt-get update --fix-missing || true; \
  done; \
  rm -rf /var/lib/apt/lists/*

WORKDIR $SRC

# ---------
# zlib (pin to tag, shallow)
# ---------
RUN set -eux; \
  for i in 1 2 3 4 5; do \
    rm -rf zlib; \
    git clone --depth 1 --branch v1.2.13 https://github.com/madler/zlib.git zlib && break; \
    echo "git clone zlib failed, retry $i/5" >&2; \
    sleep 10; \
  done; \
  test -d zlib

# ---------
# libpng (prefer a known tag; fallback to default branch)
# Note: 原始 benchmark 没 pin 版本；这里不改 yaml 的前提下，只做更稳的 clone。
# 你如果想 pin，可把 v1.6.33 改成你期望的 tag（不影响 yaml）。
# ---------
ARG LIBPNG_TAG=v1.6.33
RUN set -eux; \
  for i in 1 2 3 4 5; do \
    rm -rf libpng; \
    ( git clone --depth 1 --branch "${LIBPNG_TAG}" https://github.com/glennrp/libpng.git libpng \
      || git clone --depth 1 https://github.com/glennrp/libpng.git libpng ) \
    && break; \
    echo "git clone libpng failed, retry $i/5" >&2; \
    sleep 10; \
  done; \
  test -d libpng

# ---------
# Use upstream OSS-Fuzz build script as FuzzBench build.sh
# ---------
RUN set -eux; \
  test -f libpng/contrib/oss-fuzz/build.sh; \
  cp libpng/contrib/oss-fuzz/build.sh "$SRC/build.sh"

WORKDIR $SRC/libpng

# ---------
# Dictionary (retry; respects HTTP(S)_PROXY if set)
# ---------
RUN set -eux; \
  url="https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/png.dict"; \
  for i in 1 2 3 4 5; do \
    rm -f "$OUT/libpng_read_fuzzer.dict"; \
    if command -v curl >/dev/null 2>&1; then \
      curl -fL --retry 8 --retry-delay 3 --connect-timeout 20 --max-time 600 -o "$OUT/libpng_read_fuzzer.dict" "$url" && break; \
    else \
      wget --no-check-certificate -O "$OUT/libpng_read_fuzzer.dict" --tries=8 --timeout=60 "$url" && break; \
    fi; \
    echo "dict download failed, retry $i/5" >&2; \
    sleep 10; \
  done; \
  test -s "$OUT/libpng_read_fuzzer.dict"

# seeds 与其余文件（保持原行为）
ADD seeds /opt/seeds
COPY * $SRC/