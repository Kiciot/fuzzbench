# Copyright 2017 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---- Proxy: keep for git/curl only; APT will explicitly ignore it ----
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# ---- APT robustness: retries/timeouts; force APT to ignore proxy ----
RUN set -eux; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    apt-get update; \
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates git cmake ninja-build g++ libz-dev; \
  rm -rf /var/lib/apt/lists/*

# ---- GIT robustness: tolerate slow links ----
RUN set -eux; \
  git config --global http.proxy "${HTTP_PROXY}"; \
  git config --global https.proxy "${HTTPS_PROXY}"; \
  git config --global http.sslVerify false; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  git config --global http.postBuffer 524288000; \
  git config --global core.compression 0; \
  git config --global http.version HTTP/1.1

ARG BLOATY_REPO=https://github.com/google/bloaty.git
ARG BLOATY_COMMIT=52948c107c8f81045e7f9223ec02706b19cfa882
ARG GIT_CLONE_RETRIES=6

# ---- Fetch pinned commit with hard failure if never succeeds ----
RUN set -eux; \
  ok=0; \
  for i in $(seq 1 "${GIT_CLONE_RETRIES}"); do \
    rm -rf /src/bloaty; \
    mkdir -p /src/bloaty; \
    git init /src/bloaty; \
    git -C /src/bloaty remote add origin "${BLOATY_REPO}"; \
    if git -C /src/bloaty fetch --depth 1 origin "${BLOATY_COMMIT}"; then \
      git -C /src/bloaty checkout -f FETCH_HEAD; \
      ok=1; \
      break; \
    fi; \
    echo "[bloaty] fetch failed (attempt ${i}/${GIT_CLONE_RETRIES}), retrying..." >&2; \
    sleep $((i*i)); \
  done; \
  test "$ok" = "1"; \
  test -f /src/bloaty/CMakeLists.txt

# ---- Optional: pre-fetch submodules (reduces later build flakiness) ----
RUN set -eux; \
  if [ -f /src/bloaty/.gitmodules ]; then \
    ok=0; \
    for i in $(seq 1 4); do \
      if git -C /src/bloaty submodule update --init --recursive; then \
        ok=1; \
        break; \
      fi; \
      echo "[bloaty] submodule update failed (attempt ${i}/4), retrying..." >&2; \
      sleep $((i*i)); \
    done; \
    test "$ok" = "1"; \
  fi

WORKDIR /src/bloaty
COPY build.sh $SRC/