# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
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
# Tooling install (with retries)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        make \
        curl \
        wget \
        git \
        xz-utils \
      && break; \
      echo "apt-get failed, retry $i/5"; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
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
# Install CMake (pinned) with retries
# -----------------------------
RUN set -eux; \
    url="https://github.com/Kitware/CMake/releases/download/v3.14.5/cmake-3.14.5-Linux-x86_64.sh"; \
    for i in 1 2 3 4 5; do \
      rm -f /tmp/cmake.sh; \
      wget -O /tmp/cmake.sh \
        --tries=5 --timeout=60 \
        -e use_proxy=yes -e http_proxy="${HTTP_PROXY}" -e https_proxy="${HTTPS_PROXY}" \
        "${url}" && break; \
      echo "wget cmake failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -s /tmp/cmake.sh; \
    chmod +x /tmp/cmake.sh; \
    /tmp/cmake.sh --skip-license --prefix="/usr/local"; \
    rm -f /tmp/cmake.sh

# -----------------------------
# Fetch jsoncpp (shallow clone + retries)
# -----------------------------
WORKDIR $SRC
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf jsoncpp; \
      git clone --depth 1 --filter=blob:none \
        https://github.com/open-source-parsers/jsoncpp jsoncpp && break; \
      echo "git clone jsoncpp failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d jsoncpp

WORKDIR $SRC/jsoncpp

# Copy build script last for better Docker layer caching
COPY build.sh $SRC/