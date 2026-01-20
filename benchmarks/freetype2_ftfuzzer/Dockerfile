# Copyright 2020 Google LLC
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
# Tooling install (with fallback)
# -----------------------------
RUN set -eux; \
    apt-get update || (sleep 5 && apt-get update); \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y || true; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      curl \
      xz-utils \
      make \
      autoconf \
      automake \
      libtool \
    || (sleep 10 && apt-get update --fix-missing && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          ca-certificates git wget curl xz-utils make autoconf automake libtool); \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git robustness (proxy + low-speed + retry friendly)
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

# -----------------------------
# Fetch sources (use retry loops)
# -----------------------------
WORKDIR $SRC

# 1) freetype
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf freetype2; \
      git clone --depth 1 --filter=blob:none https://github.com/freetype/freetype.git freetype2 && break; \
      echo "git clone freetype failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -d freetype2

# 2) text-rendering-tests (TRT)
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf TRT; \
      git clone --depth 1 --filter=blob:none https://github.com/unicode-org/text-rendering-tests.git TRT && break; \
      echo "git clone TRT failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -d TRT

# 3) libarchive tarball (avoid --no-check-certificate; do proper TLS)
#    If your proxy does MITM TLS and breaks validation, THEN consider adding back --no-check-certificate,
#    but first try with ca-certificates (installed above).
RUN set -eux; \
    url="https://github.com/libarchive/libarchive/releases/download/v3.4.3/libarchive-3.4.3.tar.xz"; \
    for i in 1 2 3 4 5; do \
      rm -f libarchive-3.4.3.tar.xz; \
      wget -O libarchive-3.4.3.tar.xz \
        --tries=5 --timeout=60 \
        -e use_proxy=yes -e http_proxy="${HTTP_PROXY}" -e https_proxy="${HTTPS_PROXY}" \
        "${url}" && break; \
      echo "wget libarchive failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -s libarchive-3.4.3.tar.xz

# Copy build scripts/configs last to maximize Docker layer cache hit rate
COPY * $SRC/