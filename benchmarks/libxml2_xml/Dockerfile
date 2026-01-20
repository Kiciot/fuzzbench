# Copyright 2020 Google LLC
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
# Base deps (with retries)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        git \
        make autoconf libtool pkg-config \
        zlib1g-dev zlib1g-dev:i386 \
        liblzma-dev liblzma-dev:i386 \
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
# Automake 1.16.x (prefer apt, fallback to .deb)
# -----------------------------
# Your original comment said "requires automake 1.16.3".
# We install 1.16.*; first try distro package, then fallback to the pinned .deb.
RUN set -eux; \
    if ! command -v automake >/dev/null 2>&1; then :; fi; \
    if automake --version 2>/dev/null | head -n1 | grep -q ' 1\.16\.'; then \
      echo "automake already 1.16.x"; \
    else \
      ( \
        apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends automake \
      ) || true; \
      if automake --version 2>/dev/null | head -n1 | grep -q ' 1\.16\.'; then \
        echo "automake installed from apt"; \
      else \
        url="http://mirrors.kernel.org/ubuntu/pool/main/a/automake-1.16/automake_1.16.5-1.3_all.deb"; \
        for i in 1 2 3 4 5; do \
          rm -f /tmp/automake.deb; \
          curl -fsSL --connect-timeout 20 --max-time 300 \
            --retry 8 \
            -o /tmp/automake.deb "${url}" && break; \
          echo "curl automake.deb failed, retry $i/5"; \
          sleep 10; \
        done; \
        test -s /tmp/automake.deb; \
        apt-get update; \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/automake.deb; \
        rm -f /tmp/automake.deb; \
      fi; \
      rm -rf /var/lib/apt/lists/*; \
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