# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd
# ----------------------------
# Proxy (only for tools that need it: git/wget/curl)
# ----------------------------
ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ----------------------------
# System deps (APT: DO NOT use proxy to avoid 502 from your local proxy)
# ----------------------------
RUN set -eux; \
  export DEBIAN_FRONTEND=noninteractive; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    apt-get update; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    apt-get install -y --no-install-recommends \
      autoconf \
      automake \
      make \
      wget \
      ca-certificates \
      git \
    ; \
  rm -rf /var/lib/apt/lists/*

# ----------------------------
# Git robustness + proxy for git only
# ----------------------------
RUN set -eux; \
  git config --global http.version HTTP/1.1; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  git config --global core.compression 0; \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY:-$HTTP_PROXY}"; \
  fi

# ----------------------------
# Fetch re2 (optionally pin commit)
# ----------------------------
ARG RE2_COMMIT=""   # e.g. "a1b2c3..." (optional). Leave empty to use HEAD.
RUN set -eux; \
  rm -rf /src/re2; \
  mkdir -p /src; \
  cd /src; \
  if [[ -z "${RE2_COMMIT}" ]]; then \
    git clone --depth 1 https://github.com/google/re2.git; \
  else \
    git init re2; \
    cd re2; \
    git remote add origin https://github.com/google/re2.git; \
    git fetch --depth 1 origin "${RE2_COMMIT}"; \
    git checkout -q FETCH_HEAD; \
  fi

# ----------------------------
# Dictionary (wget uses proxy; ok)
# ----------------------------
RUN set -eux; \
  wget -qO "$OUT/fuzzer.dict" \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/regexp.dict

COPY build.sh target.cc $SRC/