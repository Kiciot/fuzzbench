# Copyright 2016 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ARG GIT_SSL_NO_VERIFY=0

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# APT: mirror + retries + timeouts (cover sources.list and sources.list.d)
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do \
      [ -f "$f" ] || continue; \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' "$f" || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' "$f" || true; \
    done; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# Install deps with retry loop
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get upgrade -y || true; \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        make autoconf automake libtool \
        curl \
        tcl \
        zlib1g-dev \
        git \
        zip unzip \
      && break; \
      echo "apt-get failed, retry $i/5"; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Git robustness
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

# Fetch sqlite source (curl 7.68 compatible retry strategy)
RUN set -eux; \
    mkdir -p "$SRC/sqlite3"; \
    cd "$SRC/sqlite3"; \
    for i in 1 2 3 4 5; do \
      rm -f sqlite3.tar.gz; \
      if curl -fsSL \
        --retry 12 \
        --retry-connrefused \
        --retry-delay 5 \
        --retry-max-time 1200 \
        --connect-timeout 20 \
        --max-time 1200 \
        'https://sqlite.org/src/tarball/sqlite.tar.gz?r=c78cbf2e86850cc6' \
        -o sqlite3.tar.gz; then \
        break; \
      fi; \
      echo "curl sqlite tarball failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -s sqlite3.tar.gz; \
    tar xzf sqlite3.tar.gz --strip-components 1; \
    rm -f sqlite3.tar.gz

# Build seed corpus safely
RUN set -eux; \
    cd "$SRC/sqlite3"; \
    find . -name "*.test" -print0 | xargs -0 -r -I{} printf '%s\n' "{}" | zip -q "$SRC/ossfuzz_seed_corpus.zip" -@

WORKDIR $SRC/sqlite3
COPY build.sh *.dict $SRC/