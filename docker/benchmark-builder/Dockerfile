# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ARG parent_image

# Using multi-stage build to copy latest Python 3.
FROM gcr.io/fuzzbench/base-image AS base-image

FROM $parent_image

ARG fuzzer
ARG benchmark
ARG debug_builder

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV FUZZER=$fuzzer \
    BENCHMARK=$benchmark \
    DEBUG_BUILDER=$debug_builder \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT robustness (retries/timeouts)
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# Install dependencies required by Python3 or Pip3 (retry loop to tolerate proxy flakiness)
RUN set -eux; \
    for i in 1 2 3 4 5 6 7 8; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get upgrade -y && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xz-utils \
        zlib1g-dev \
        libssl-dev \
        libffi-dev \
      && break; \
      echo "apt-get failed ($i/8), retrying..."; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Remove old python3.8 artifacts from parent image (ignore if missing)
RUN set -eux; \
    rm -rf \
      /usr/local/bin/python3.8* \
      /usr/local/bin/pip3 \
      /usr/local/lib/python3.8 \
      /usr/local/include/python3.8 \
      /usr/local/lib/python3.8/site-packages \
      || true

# Copy latest python3 from base-image into local.
COPY --from=base-image /usr/local/bin/python3* /usr/local/bin/
COPY --from=base-image /usr/local/bin/pip3* /usr/local/bin/
COPY --from=base-image /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=base-image /usr/local/include/python3.10 /usr/local/include/python3.10
COPY --from=base-image /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy the entire fuzzers directory tree to allow for module dependencies.
COPY fuzzers $SRC/fuzzers

# Disable LeakSanitizer since ptrace is unavailable in Google Cloud build
# and is not needed during build process.
ENV ASAN_OPTIONS="detect_leaks=0"

COPY benchmarks/$benchmark/benchmark.yaml /

RUN mkdir -p /opt/fuzzbench/
COPY docker/benchmark-builder/checkout_commit.py /opt/fuzzbench/

# Checkout pinned commit
RUN set -eux; \
    CHECKOUT_COMMIT="$(tr -d ' ' < /benchmark.yaml | grep '^commit:' | cut -d ':' -f2)"; \
    python3 -u /opt/fuzzbench/checkout_commit.py "$CHECKOUT_COMMIT" "$SRC"

COPY docker/benchmark-builder/fuzzer_build /usr/bin/fuzzer_build

RUN echo "Run fuzzer_build to build the target" && \
    if [ -z "$debug_builder" ] ; then fuzzer_build; fi