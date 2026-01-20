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
# Base deps + automake 1.16.5 (HARD REQUIREMENT)
# -----------------------------
# focal 默认 automake=1.16.1 -> 会触发 libxml2 的 "require Automake 1.16.3" 错误
# 这里明确安装 1.16.5（优先 apt 的 updates，失败再用 .deb 兜底），并做版本断言。
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && break || true; \
      echo "apt-get update failed, retry $i/5"; \
      sleep 10; \
    done; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl wget git \
      make autoconf libtool pkg-config \
      zlib1g-dev zlib1g-dev:i386 \
      liblzma-dev liblzma-dev:i386; \
    \
    # 1) 尝试从 apt 装 automake 1.16.5（在 focal-updates 通常是 1.16.1-4ubuntu6）
    #    但仍可能因为镜像/网络失败，所以要兜底。
    (DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends automake) || true; \
    \
    # 2) 如果不是 >=1.16.3，则用 .deb 强制升级到 1.16.5
    ver_ok=0; \
    if command -v automake >/dev/null 2>&1; then \
      v="$(automake --version | head -n1 | awk '{print $NF}')"; \
      dpkg --compare-versions "$v" ge "1.16.3" && ver_ok=1 || true; \
    fi; \
    if [ "$ver_ok" -ne 1 ]; then \
      echo "automake too old, forcing 1.16.5 via .deb"; \
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
    # 3) 版本断言：必须 >= 1.16.3，否则直接失败（避免后面 autoreconf 才爆）
    v="$(automake --version | head -n1 | awk '{print $NF}')"; \
    dpkg --compare-versions "$v" ge "1.16.3"; \
    echo "automake version OK: $v"; \
    \
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
# Fetch libxml2 (with retries)
# -----------------------------
WORKDIR $SRC
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libxml2; \
      git clone --depth 1 --filter=blob:none \
        https://gitlab.gnome.org/GNOME/libxml2.git libxml2 && break; \
      echo "git clone libxml2 failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d libxml2

WORKDIR $SRC/libxml2
COPY build.sh $SRC/