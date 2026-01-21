# Copyright 2019 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT stability: retries/timeouts
# -----------------------------
RUN set -eux; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Base deps
# -----------------------------
RUN set -eux; \
  for i in 1 2 3 4 5; do \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      wget \
      xz-utils \
      make \
      gcc \
      g++ \
      texinfo \
      bison \
      flex \
      file \
    && break; \
    echo "apt-get failed, retry $i/5"; \
    sleep 10; \
    apt-get update --fix-missing || true; \
  done; \
  rm -rf /var/lib/apt/lists/*

# -----------------------------
# Helper: download-with-retry (no curl new flags)
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
'for url in "$url1" "$url2" "$url3"; do' \
'  [ -n "$url" ] || continue' \
'  i=1' \
'  while [ "$i" -le 8 ]; do' \
'    rm -f "$out"' \
'    if curl -fL --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 600 -o "$out" "$url"; then' \
'      exit 0' \
'    fi' \
'    echo "download failed ($i/8): $url" >&2' \
'    i=$((i+1))' \
'    sleep 5' \
'  done' \
'done' \
'echo "download permanently failed (all mirrors): $url1" >&2' \
'exit 1' \
  > /usr/local/bin/_dl_retry; \
  chmod +x /usr/local/bin/_dl_retry

# -----------------------------
# Fetch & build binutils (release tarball, avoid git clone)
# -----------------------------
ENV BINUTILS_VER=2.28

WORKDIR /tmp
RUN set -eux; \
  _dl_retry \
    "https://ftp.gnu.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.xz" \
    "https://ftpmirror.gnu.org/binutils/binutils-${BINUTILS_VER}.tar.xz" \
    "https://mirrors.kernel.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.xz" \
    "/tmp/binutils.tar.xz"; \
  tar -xf /tmp/binutils.tar.xz; \
  rm -f /tmp/binutils.tar.xz; \
  mkdir -p "/tmp/binutils-build"; \
  cd "/tmp/binutils-build"; \
  "../binutils-${BINUTILS_VER}/configure" --disable-nls --disable-werror; \
  make -j"$(nproc)"; \
  make install; \
  cd /; \
  rm -rf "/tmp/binutils-${BINUTILS_VER}" "/tmp/binutils-build"

# FuzzBench build.sh will compile the fuzzer target using installed objdump.
WORKDIR $SRC
COPY build.sh $SRC/