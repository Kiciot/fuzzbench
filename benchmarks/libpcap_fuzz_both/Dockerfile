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

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1
ARG GIT_SSL_NO_VERIFY=0

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# deps
# -----------------------------
RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      make cmake flex bison git ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git proxy (optional) + ssl verify switch
# -----------------------------
RUN set -eux; \
    if [ -n "${HTTP_PROXY}" ]; then git config --global http.proxy "${HTTP_PROXY}"; fi; \
    if [ -n "${HTTPS_PROXY}" ]; then git config --global https.proxy "${HTTPS_PROXY}"; fi; \
    if [ "${GIT_SSL_NO_VERIFY}" = "1" ]; then git config --global http.sslVerify false; fi

# -----------------------------
# sources (same as original)
# -----------------------------
RUN git clone https://github.com/the-tcpdump-group/libpcap.git libpcap

# For corpus as wireshark.
RUN git clone https://github.com/the-tcpdump-group/tcpdump.git tcpdump && \
    git -C tcpdump checkout 032e4923e5202ea4d5a6d1cead83ed1927135874

WORKDIR $SRC
COPY build.sh $SRC/