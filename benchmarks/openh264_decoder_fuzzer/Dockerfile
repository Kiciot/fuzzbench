FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# 1) 代理环境：保留给 git/curl 等用
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}
ENV no_proxy=${NO_PROXY}

MAINTAINER twsmith@mozilla.com

# 2) 关键：apt 配置
# - 全局仍可用代理
# - 但对 archive.ubuntu.com / security.ubuntu.com 走 DIRECT（绕开代理，避免 7890 超时）
# - 增加重试与超时
RUN set -eux; \
  printf '%s\n' \
    "Acquire::Retries \"5\";" \
    "Acquire::http::Timeout \"60\";" \
    "Acquire::https::Timeout \"60\";" \
    "Acquire::http::Proxy \"${HTTP_PROXY}\";" \
    "Acquire::https::Proxy \"${HTTPS_PROXY}\";" \
    "Acquire::http::Proxy::archive.ubuntu.com \"DIRECT\";" \
    "Acquire::http::Proxy::security.ubuntu.com \"DIRECT\";" \
    "Acquire::https::Proxy::archive.ubuntu.com \"DIRECT\";" \
    "Acquire::https::Proxy::security.ubuntu.com \"DIRECT\";" \
    > /etc/apt/apt.conf.d/99proxy

# 3) 安装依赖（加上 --no-install-recommends + 清理，减少体积/失败面）
RUN set -eux; \
    dpkg --add-architecture i386; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libstdc++-9-dev libstdc++-9-dev:i386 nasm subversion; \
    rm -rf /var/lib/apt/lists/*

# 4) git 继续走代理（如果你需要）
RUN git config --global http.proxy "${HTTP_PROXY}" \
 && git config --global https.proxy "${HTTPS_PROXY}"

RUN git clone https://github.com/cisco/openh264.git

WORKDIR openh264
COPY build.sh decoder_fuzzer.cpp $SRC/