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

# ---- APT: do NOT use proxy (most stable), add retries/timeouts ----
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
      apt-get install -y --no-install-recommends libcap-dev; \
    rm -rf /var/lib/apt/lists/*

# ---- Git: use proxy, but harden against slow links ----
RUN set -eux; \
    git config --global http.proxy "$HTTP_PROXY"; \
    git config --global https.proxy "$HTTPS_PROXY"; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global http.version HTTP/1.1

# Clone systemd (keep shallow clone)
RUN set -eux; \
    git clone --depth 1 --branch v252 https://github.com/systemd/systemd; \
    cp $SRC/systemd/tools/oss-fuzz.sh $SRC/build.sh; \
    # Move shared libraries and tweak rpath for all $ARCHITECTURE.
    sed -i '119d;126d' $SRC/build.sh

WORKDIR systemd