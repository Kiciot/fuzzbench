FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

RUN set -eux; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-fuzzbench-retries

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
      zip \
      binutils \
    && break; \
    echo "apt-get failed, retry $i/5"; \
    sleep 10; \
    apt-get update --fix-missing || true; \
  done; \
  rm -rf /var/lib/apt/lists/*

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
'    if curl -fL --retry 3 --retry-delay 3 --connect-timeout 20 --max-time 600 -o "$out" "$url"; then exit 0; fi' \
'    echo "download failed ($i/8): $url" >&2' \
'    i=$((i+1))' \
'    sleep 5' \
'  done' \
'done' \
'echo "download permanently failed (all mirrors): $url1" >&2' \
'exit 1' \
  > /usr/local/bin/_dl_retry; \
  chmod +x /usr/local/bin/_dl_retry

ENV BINUTILS_VER=2.28

# Put the extracted source at ${SRC}/binutils so build.sh can reuse it without re-downloading.
WORKDIR /tmp
RUN set -eux; \
  _dl_retry \
    "https://ftp.gnu.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.gz" \
    "https://ftpmirror.gnu.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.gz" \
    "https://mirrors.kernel.org/gnu/binutils/binutils-${BINUTILS_VER}.tar.gz" \
    "/tmp/binutils.tar.gz"; \
  mkdir -p "${SRC}"; \
  tar -xf /tmp/binutils.tar.gz -C "${SRC}"; \
  rm -f /tmp/binutils.tar.gz; \
  rm -rf "${SRC}/binutils"; \
  mv "${SRC}/binutils-${BINUTILS_VER}" "${SRC}/binutils"

WORKDIR ${SRC}
COPY build.sh ${SRC}/build.sh
RUN chmod +x ${SRC}/build.sh