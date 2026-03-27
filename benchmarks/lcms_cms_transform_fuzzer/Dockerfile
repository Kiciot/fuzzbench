# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---- proxy for git/wget only ----
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# ---- apt: mirror + no proxy ----
RUN set -eux; \
  sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
  sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get update; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get install -y --no-install-recommends \
    make automake libtool wget ca-certificates git; \
  rm -rf /var/lib/apt/lists/*

# ---- git robust ----
RUN set -eux; \
  git config --global http.proxy "$HTTP_PROXY"; \
  git config --global https.proxy "$HTTPS_PROXY"; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  git config --global http.postBuffer 524288000

# pin repo (建议你锁定 commit，避免 master 漂移)
RUN set -eux; \
  git clone --depth 1 https://github.com/mm2/Little-CMS.git /src/Little-CMS

RUN set -eux; \
  wget -qO /out/cms_transform_fuzzer.dict \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/icc.dict

COPY cms_transform_fuzzer.cc build.sh /src/
ADD seeds /opt/seeds