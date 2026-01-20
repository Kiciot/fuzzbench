# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ========================
# 网络/代理（构建期可配置）
# ========================
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ========================
# APT 稳定性：换源 + retries + timeout
# ========================
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
    fi; \
    printf 'Acquire::Retries "8";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::http::Pipeline-Depth "0";\n' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# ========================
# Git：代理 + 低速保护 +（可选）关闭 SSL 校验
# ========================
ARG GIT_SSL_NO_VERIFY=0
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

# ========================
# 依赖安装（带重试）
# ========================
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        make \
        autoconf \
        automake \
        libtool \
        zlib1g-dev \
        git \
        wget \
        curl \
      && break; \
      echo "apt-get failed, retry $i/5"; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# ========================
# 拉取 zlib（保持你原来成功路径）
# ========================
WORKDIR $SRC
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf zlib; \
      git clone --depth 1 --branch v1.2.13 https://github.com/madler/zlib.git zlib && break; \
      echo "git clone zlib failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d zlib

# ========================
# 拉取 libpng（加 depth，并做 branch/tag fallback）
# ========================
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libpng; \
      ( git clone --depth 1 --branch v1.6.33 https://github.com/glennrp/libpng.git libpng \
        || git clone --depth 1 https://github.com/glennrp/libpng.git libpng ) \
      && break; \
      echo "git clone libpng failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d libpng

# 调试：确认 oss-fuzz 目录存在（失败就打印目录树）
RUN set -eux; \
    ls -R libpng/contrib/oss-fuzz || (echo "libpng/contrib/oss-fuzz missing"; ls -R libpng/contrib || true; exit 1)

# 拷贝 build.sh 到 $SRC（OSS-Fuzz/FuzzBench 期望）
RUN set -eux; \
    cp libpng/contrib/oss-fuzz/build.sh "$SRC/build.sh"

WORKDIR $SRC/libpng

# ========================
# 下载 dict（显式代理；允许失败重试）
# ========================
RUN set -eux; \
    url="https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/png.dict"; \
    for i in 1 2 3 4 5; do \
      rm -f "$OUT/libpng_read_fuzzer.dict"; \
      wget -O "$OUT/libpng_read_fuzzer.dict" \
        --tries=5 --timeout=60 \
        -e use_proxy=yes \
        -e http_proxy="${HTTP_PROXY}" \
        -e https_proxy="${HTTPS_PROXY}" \
        --no-check-certificate \
        "${url}" && break; \
      echo "wget dict failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -s "$OUT/libpng_read_fuzzer.dict"

# seeds 与其余文件
ADD seeds /opt/seeds
COPY * $SRC/