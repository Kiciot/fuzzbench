# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

# 仅给后续 git/curl 使用；apt 会显式 env -u 去掉代理
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- APT: 不走代理 + 更稳健的源 ----
RUN set -eux; \
    # 可选：替换为清华源（适用于 Ubuntu focal）
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    # APT 重试/超时
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      > /etc/apt/apt.conf.d/80-retries; \
    # 关键：apt 强制忽略代理
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get update; \
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
      apt-get install -y --no-install-recommends \
        make autoconf automake libtool g++ \
        sqlite3 libsqlite3-dev \
        pkg-config wget ca-certificates \
        liblzma-dev; \
    rm -rf /var/lib/apt/lists/*

# ---- GIT: 走代理 + 更稳健 ----
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    # 降低网络抖动导致的失败概率
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 120; \
    git config --global http.postBuffer 104857600; \
    git config --global core.compression 0

# PROJ：未锁定 commit，直接浅克隆即可
RUN set -eux; \
    git clone --depth 1 https://github.com/OSGeo/PROJ PROJ

# curl：需要固定 commit，用浅克隆+fetch 指定 commit
RUN set -eux; \
    git init PROJ/curl; \
    git -C PROJ/curl remote add origin https://github.com/curl/curl.git; \
    git -C PROJ/curl fetch --depth 1 origin c12fb3ddaf48e709a7a4deaa55ec485e4df163ee; \
    git -C PROJ/curl checkout FETCH_HEAD

# libtiff：同理（gitlab）
RUN set -eux; \
    git init PROJ/libtiff; \
    git -C PROJ/libtiff remote add origin https://gitlab.com/libtiff/libtiff.git; \
    git -C PROJ/libtiff fetch --depth 1 origin c8e1289deff3fa60ba833ccec6c030934b02c281; \
    git -C PROJ/libtiff checkout FETCH_HEAD

WORKDIR PROJ

COPY third_party/build.sh $SRC/

# This is to fix Fuzz Introspector build by using LLVM old pass manager
ENV OLD_LLVMPASS 1