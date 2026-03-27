# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# ...
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ===== Proxy (kept for git/curl; apt can also use it if稳定) =====
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# ===== APT robustness =====
RUN set -eux; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  apt-get update; \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    cmake \
    ninja-build \
    g++ \
    libz-dev \
  ; \
  rm -rf /var/lib/apt/lists/*

# ===== GIT robustness =====
RUN set -eux; \
  git config --global http.proxy "${HTTP_PROXY}"; \
  git config --global https.proxy "${HTTPS_PROXY}"; \
  git config --global http.sslVerify false; \
  # 避免“60秒低速<1000B/s就断”的典型报错
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  # 减少大对象/pack 时的失败概率
  git config --global http.postBuffer 104857600; \
  git config --global core.compression 0

# ===== Checkout pinned commit with retries (shallow fetch) =====
ARG BLOATY_REPO=https://github.com/google/bloaty.git
ARG BLOATY_COMMIT=52948c107c8f81045e7f9223ec02706b19cfa882
ARG GIT_CLONE_RETRIES=6

RUN set -eux; \
  for i in $(seq 1 "${GIT_CLONE_RETRIES}"); do \
    rm -rf /src/bloaty && mkdir -p /src/bloaty; \
    git init /src/bloaty; \
    git -C /src/bloaty remote add origin "${BLOATY_REPO}"; \
    # 尝试浅抓取指定 commit（最省流量）；失败就退避重试
    if git -C /src/bloaty fetch --depth 1 origin "${BLOATY_COMMIT}"; then \
      git -C /src/bloaty checkout -f FETCH_HEAD; \
      break; \
    fi; \
    echo "bloaty fetch failed (attempt ${i}/${GIT_CLONE_RETRIES}), retrying..."; \
    sleep $((i*i)); \
  done; \
  test -d /src/bloaty/.git

WORKDIR /src/bloaty
COPY build.sh $SRC/