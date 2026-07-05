# Copyright 2017 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---- Optional proxy/mirror for network fetches ----
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1
ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}
ENV no_proxy=${NO_PROXY}

# ---- APT robustness: optional mirror + retries/timeouts ----
RUN set -eux; \
  # 1. Optional mirror replacement when UBUNTU_APT_MIRROR is set
  if [ -n "${UBUNTU_APT_MIRROR}" ]; then \
    security_mirror="${UBUNTU_SECURITY_APT_MIRROR:-${UBUNTU_APT_MIRROR}}"; \
    sed -i "s|http://archive.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" /etc/apt/sources.list || true; \
    sed -i "s|http://security.ubuntu.com/ubuntu/|${security_mirror}/|g" /etc/apt/sources.list || true; \
  fi; \
  # 2. Write retry and timeout APT config
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  # 3. Install build dependencies
  apt-get update; \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates git cmake ninja-build g++ libz-dev; \
  rm -rf /var/lib/apt/lists/*

# ---- GIT robustness: tolerate slow links ----
RUN set -eux; \
  if [ -n "${HTTP_PROXY}" ]; then git config --global http.proxy "${HTTP_PROXY}"; fi; \
  if [ -n "${HTTPS_PROXY}" ]; then git config --global https.proxy "${HTTPS_PROXY}"; fi; \
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