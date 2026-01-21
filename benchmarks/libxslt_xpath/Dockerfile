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
ARG GIT_SSL_NO_VERIFY=1

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT stability: mirror + retries + timeouts
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
    fi; \
    printf 'Acquire::Retries "8";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::http::Pipeline-Depth "0";\n' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Toolchain versions (manual build)
# -----------------------------
ENV M4_VERSION=1.4.19
ENV AUTOCONF_VERSION=2.71
ENV AUTOMAKE_VERSION=1.16.5

# -----------------------------
# Base deps + robust installs
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        curl \
        git \
        make \
        libtool \
        pkg-config \
        libgcrypt-dev \
        xz-utils \
        flex \
        bison \
        zip \
      && break; \
      echo "apt-get failed, retry $i/5" >&2; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    update-ca-certificates || true; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git robustness (proxy + optional SSL verify off)
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    if [ "${GIT_SSL_NO_VERIFY}" = "1" ]; then \
      git config --global http.sslVerify false; \
    fi

# -----------------------------
# Helper: download-with-retry (curl + mirror fallback)
# Usage:
#   _dl_retry <url1> [url2] [url3] <out>
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
'    if curl -fL --retry 3 --retry-all-errors --connect-timeout 15 --max-time 300 -o "$out" "$url"; then' \
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
# Build m4 (mirror fallback)
# -----------------------------
RUN set -eux; \
    _dl_retry \
      "https://ftp.gnu.org/gnu/m4/m4-${M4_VERSION}.tar.gz" \
      "https://ftpmirror.gnu.org/m4/m4-${M4_VERSION}.tar.gz" \
      "https://mirrors.kernel.org/gnu/m4/m4-${M4_VERSION}.tar.gz" \
      "/tmp/m4.tar.gz"; \
    tar -C /tmp -xf /tmp/m4.tar.gz; \
    rm -f /tmp/m4.tar.gz; \
    cd "/tmp/m4-${M4_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/m4-${M4_VERSION}"

# -----------------------------
# Build autoconf (mirror fallback)
# -----------------------------
RUN set -eux; \
    _dl_retry \
      "https://ftp.gnu.org/gnu/autoconf/autoconf-${AUTOCONF_VERSION}.tar.gz" \
      "https://ftpmirror.gnu.org/autoconf/autoconf-${AUTOCONF_VERSION}.tar.gz" \
      "https://mirrors.kernel.org/gnu/autoconf/autoconf-${AUTOCONF_VERSION}.tar.gz" \
      "/tmp/autoconf.tar.gz"; \
    tar -C /tmp -xf /tmp/autoconf.tar.gz; \
    rm -f /tmp/autoconf.tar.gz; \
    cd "/tmp/autoconf-${AUTOCONF_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/autoconf-${AUTOCONF_VERSION}"

# -----------------------------
# Build automake (mirror fallback)
# -----------------------------
RUN set -eux; \
    _dl_retry \
      "https://ftp.gnu.org/gnu/automake/automake-${AUTOMAKE_VERSION}.tar.gz" \
      "https://ftpmirror.gnu.org/automake/automake-${AUTOMAKE_VERSION}.tar.gz" \
      "https://mirrors.kernel.org/gnu/automake/automake-${AUTOMAKE_VERSION}.tar.gz" \
      "/tmp/automake.tar.gz"; \
    tar -C /tmp -xf /tmp/automake.tar.gz; \
    rm -f /tmp/automake.tar.gz; \
    cd "/tmp/automake-${AUTOMAKE_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/automake-${AUTOMAKE_VERSION}"; \
    v="$(automake --version | head -n1 | awk '{print $NF}')" ; \
    dpkg --compare-versions "$v" ge "1.16.3"; \
    echo "automake version OK: $v"

# Use the newly installed aclocal macros.
ENV ACLOCAL_PATH=/usr/share/aclocal/

# -----------------------------
# Fetch sources (with retries)
# -----------------------------
WORKDIR $SRC

RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libxml2; \
      git clone --filter=blob:none https://gitlab.gnome.org/GNOME/libxml2.git libxml2 && break; \
      echo "git clone libxml2 failed, retry $i/5" >&2; \
      sleep 10; \
    done; \
    test -d libxml2; \
    git -C libxml2 checkout c7260a47f19e01f4f663b6a56fbdc2dafd8a6e7e

RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libxslt; \
      git clone --filter=blob:none https://gitlab.gnome.org/GNOME/libxslt.git libxslt && break; \
      echo "git clone libxslt failed, retry $i/5" >&2; \
      sleep 10; \
    done; \
    test -d libxslt

WORKDIR $SRC/libxslt
COPY build.sh $SRC/