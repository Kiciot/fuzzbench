# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

SHELL ["/bin/bash", "-exo", "pipefail", "-c"]

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
    printf 'Acquire::Retries "8";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::http::Pipeline-Depth "0";\nAcquire::https::Pipeline-Depth "0";\n' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Base deps + automake (>= 1.16.3)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && break || true; \
      echo "apt-get update failed, retry $i/5"; \
      sleep 10; \
    done; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl wget git \
      make autoconf libtool pkg-config \
      automake \
      zlib1g-dev zlib1g-dev:i386 \
      liblzma-dev liblzma-dev:i386; \
    \
    # If automake is too old, force 1.16.5 via .deb (fallback)
    ver_ok=0; \
    v="$(automake --version | head -n1 | awk '{print $NF}')" || true; \
    if [ -n "${v:-}" ] && dpkg --compare-versions "$v" ge "1.16.3"; then \
      ver_ok=1; \
    fi; \
    if [ "$ver_ok" -ne 1 ]; then \
      echo "automake too old ($v), forcing 1.16.5 via .deb"; \
      url="http://mirrors.kernel.org/ubuntu/pool/main/a/automake-1.16/automake_1.16.5-1.3_all.deb"; \
      for i in 1 2 3 4 5; do \
        rm -f /tmp/automake.deb; \
        curl -fsSL --connect-timeout 20 --max-time 300 --retry 8 \
          -o /tmp/automake.deb "${url}" && break; \
        echo "download automake.deb failed, retry $i/5"; \
        sleep 10; \
      done; \
      test -s /tmp/automake.deb; \
      apt-get update; \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/automake.deb; \
      rm -f /tmp/automake.deb; \
    fi; \
    \
    v="$(automake --version | head -n1 | awk '{print $NF}')"; \
    dpkg --compare-versions "$v" ge "1.16.3"; \
    echo "automake version OK: $v"; \
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
# Fetch libxml2 (with retries, multi-origin)
# -----------------------------
WORKDIR ${SRC}
RUN set -eux; \
    urls=( \
      "https://github.com/GNOME/libxml2.git" \
      "https://hub.fastgit.xyz/GNOME/libxml2.git" \
      "https://gitlab.gnome.org/GNOME/libxml2.git" \
    ); \
    ok=0; \
    for u in "${urls[@]}"; do \
      for i in 1 2 3 4 5; do \
        rm -rf libxml2; \
        git clone --depth 1 --filter=blob:none "$u" libxml2 && { ok=1; break; } || true; \
        echo "git clone libxml2 from $u failed, retry $i/5"; \
        sleep 10; \
      done; \
      [ "$ok" -eq 1 ] && break; \
    done; \
    test -d libxml2

WORKDIR ${SRC}/libxml2
COPY build.sh ${SRC}/