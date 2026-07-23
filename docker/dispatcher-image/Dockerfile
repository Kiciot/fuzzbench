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

ARG image_namespace=gcr.io/fuzzbench

FROM gcr.io/oss-fuzz-base/base-clang@sha256:05774d8e388cb4975662c8eb25217e38a799d720b622e5c5d8abb79a76b49e53 AS base-clang

FROM ${image_namespace}/base-image

ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV WORK /work
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY
WORKDIR $WORK

# Install runtime dependencies for benchmarks, easy json parsing, and fuzzbench.
RUN apt-get update -y && apt-get install -y \
    jq \
    libglib2.0-0 \
    libxml2 \
    libarchive13 \
    libgss3 \
    libgl1

# Install docker cli.
RUN DOCKER_VERSION=26.1.4 && \
    curl -O https://download.docker.com/linux/static/stable/x86_64/docker-$DOCKER_VERSION.tgz && \
    tar -xvzf docker-$DOCKER_VERSION.tgz && \
    mv docker/docker /usr/bin/ && \
    rm -rf docker docker-$DOCKER_VERSION.tgz

# Install docker buildx plugin required by newer Docker CLI when BuildKit is enabled.
RUN BUILDX_VERSION=0.14.1 && \
    mkdir -p /usr/libexec/docker/cli-plugins /usr/lib/docker/cli-plugins && \
    curl -fL https://github.com/docker/buildx/releases/download/v$BUILDX_VERSION/buildx-v$BUILDX_VERSION.linux-amd64 \
      -o /usr/libexec/docker/cli-plugins/docker-buildx && \
    chmod +x /usr/libexec/docker/cli-plugins/docker-buildx && \
    ln -sf /usr/libexec/docker/cli-plugins/docker-buildx /usr/lib/docker/cli-plugins/docker-buildx

# Install cloud sql proxy.
RUN curl https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 > \
    /usr/local/bin/cloud_sql_proxy
RUN chmod +x /usr/local/bin/cloud_sql_proxy

# Copy llvm-tool binaries needed for clang source-code based coverage and
# symbolization.
COPY --from=base-clang /usr/local/bin/llvm-cov /usr/local/bin/
COPY --from=base-clang /usr/local/bin/llvm-profdata /usr/local/bin/
COPY --from=base-clang /usr/local/bin/llvm-symbolizer /usr/local/bin/

COPY startup-dispatcher.sh $WORK/
