# Copyright 2018 Google Inc.
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

# ---- Proxy (keep for git/curl etc.) ----
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# ---- APT: do NOT use proxy (most stable), use TUNA mirror, add retries/timeouts ----
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
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
      apt-get install -y --no-install-recommends --fix-missing \
        ca-certificates \
        git \
        libcap-dev; \
    rm -rf /var/lib/apt/lists/*

# ---- Git: use proxy + harden; add retry wrapper ----
RUN set -eux; \
    git config --global http.proxy "$HTTP_PROXY"; \
    git config --global https.proxy "$HTTPS_PROXY"; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global http.version HTTP/1.1; \
    printf '%s\n' \
      '#!/bin/sh' \
      'set -eu' \
      'cmd="$*"' \
      'i=1' \
      'while [ "$i" -le 5 ]; do' \
      '  if sh -c "$cmd"; then exit 0; fi' \
      '  echo "[git-retry] failed ($i/5): $cmd" >&2' \
      '  i=$((i+1))' \
      '  sleep 5' \
      'done' \
      'exit 1' \
      > /usr/local/bin/_retry; \
    chmod +x /usr/local/bin/_retry

# ---- Fetch systemd v252 in a controlled way (depth=1 tag fetch), then patch build.sh ----
RUN set -eux; \
    _retry "git init /src/systemd"; \
    _retry "git -C /src/systemd remote add origin https://github.com/systemd/systemd.git"; \
    _retry "git -C /src/systemd fetch --depth 1 origin refs/tags/v252:refs/tags/v252"; \
    git -C /src/systemd checkout -q v252; \
    cp /src/systemd/tools/oss-fuzz.sh /src/build.sh; \
    sed -i '119d;126d' /src/build.sh

WORKDIR /src/systemd