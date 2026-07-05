# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1
ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- Helpers (Fixed parser issue with printf) ----
RUN set -eux; \
  printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'n="${1:-6}"; shift || true' \
    'i=1' \
    'while [ "$i" -le "$n" ]; do' \
    '  if sh -c "$*"; then exit 0; fi' \
    '  echo "[retry] failed ($i/$n): $*" >&2' \
    '  i=$((i+1))' \
    '  sleep $((i*i))' \
    'done' \
    'exit 1' \
    > /usr/local/bin/_retry; \
  chmod +x /usr/local/bin/_retry; \
  \
  printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy' \
    'export DEBIAN_FRONTEND=noninteractive' \
    'printf "%s\\n" \' \
    '  "Acquire::Retries 8;" \' \
    '  "Acquire::http::Timeout 60;" \' \
    '  "Acquire::https::Timeout 60;" \' \
    '  "Acquire::http::Pipeline-Depth 0;" \' \
    '  "Acquire::https::Pipeline-Depth 0;" \' \
    '  "Acquire::http::Proxy false;" \' \
    '  "Acquire::https::Proxy false;" \' \
    '  "DPkg::Lock::Timeout 120;" \' \
    '  > /etc/apt/apt.conf.d/80-fuzzbench-retries' \
    'i=1' \
    'while [ "$i" -le 8 ]; do' \
    '  apt-get update && \' \
    '  apt-get install -y --no-install-recommends --fix-missing "$@" && \' \
    '  exit 0' \
    '  echo "[apt] install failed ($i/8): $*" >&2' \
    '  i=$((i+1))' \
    '  sleep 5' \
    '  apt-get update --fix-missing || true' \
    'done' \
    'exit 1' \
    > /usr/local/bin/_apt_install; \
  chmod +x /usr/local/bin/_apt_install; \
  \
  printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'url="$1"; dir="$2"; ref="$3"' \
    'rm -rf "$dir" && mkdir -p "$dir"' \
    'git config --global http.proxy "${HTTP_PROXY:-}" || true' \
    'git config --global https.proxy "${HTTPS_PROXY:-}" || true' \
    'git config --global http.lowSpeedLimit 1 || true' \
    'git config --global http.lowSpeedTime 600 || true' \
    'git config --global http.postBuffer 524288000 || true' \
    'git config --global core.compression 0 || true' \
    'git config --global http.version HTTP/1.1 || true' \
    'i=1' \
    'while [ "$i" -le 6 ]; do' \
    '  rm -rf "$dir" && mkdir -p "$dir"' \
    '  git init "$dir" >/dev/null' \
    '  git -C "$dir" remote add origin "$url" >/dev/null' \
    '  if git -C "$dir" fetch --depth 1 origin "$ref"; then' \
    '    git -C "$dir" checkout -f FETCH_HEAD >/dev/null' \
    '    exit 0' \
    '  fi' \
    '  echo "[git] fetch failed ($i/6): $url $ref" >&2' \
    '  i=$((i+1))' \
    '  sleep $((i*i))' \
    'done' \
    'exit 1' \
    > /usr/local/bin/_git_fetch_checkout; \
  chmod +x /usr/local/bin/_git_fetch_checkout; \
  \
  printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'url1="$1"; url2="${2:-}"; url3="${3:-}"; out="$4"' \
    '[ -n "$url1" ] && [ -n "$out" ] || { echo "usage: _curl_dl <url1> [url2] [url3] <out>" >&2; exit 2; }' \
    'try_one() {' \
    '  url="$1"' \
    '  [ -n "$url" ] || return 1' \
    '  rm -f "$out"' \
    '  curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 \' \
    '       --connect-timeout 20 --max-time 600 \' \
    '       -o "$out" "$url" && test -s "$out"' \
    '}' \
    'for url in "$url1" "$url2" "$url3"; do' \
    '  i=1' \
    '  while [ "$i" -le 3 ]; do' \
    '    if try_one "$url"; then exit 0; fi' \
    '    echo "[curl] failed ($i/3): $url" >&2' \
    '    i=$((i+1))' \
    '    sleep 3' \
    '  done' \
    'done' \
    'echo "download permanently failed (all mirrors): $url1" >&2' \
    'exit 1' \
    > /usr/local/bin/_curl_dl; \
  chmod +x /usr/local/bin/_curl_dl

# ---- APT: optional mirror ----
RUN set -eux; \
  if [ -n "${UBUNTU_APT_MIRROR}" ]; then \
    security_mirror="${UBUNTU_SECURITY_APT_MIRROR:-${UBUNTU_APT_MIRROR}}"; \
    sed -i "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_APT_MIRROR}|g" /etc/apt/sources.list || true; \
    sed -i "s|http://security.ubuntu.com/ubuntu|${security_mirror}|g" /etc/apt/sources.list || true; \
  fi; \
  /usr/local/bin/_apt_install \
    ca-certificates git curl xz-utils \
    make autoconf automake libtool pkg-config

WORKDIR $SRC

# 1) freetype
RUN set -eux; \
  /usr/local/bin/_git_fetch_checkout https://github.com/freetype/freetype.git freetype2 HEAD

# 2) TRT
RUN set -eux; \
  /usr/local/bin/_git_fetch_checkout https://github.com/unicode-org/text-rendering-tests.git TRT HEAD

# 3) libarchive tarball
RUN set -eux; \
  /usr/local/bin/_curl_dl \
    "https://github.com/libarchive/libarchive/releases/download/v3.4.3/libarchive-3.4.3.tar.xz" \
    "https://registry.npmmirror.com/-/binary/libarchive/3.4.3/libarchive-3.4.3.tar.xz" \
    "" \
    "libarchive-3.4.3.tar.xz"

COPY . $SRC/