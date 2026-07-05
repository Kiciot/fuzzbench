# Copyright 2020 Google LLC
# ... (License header) ...

ARG parent_image
FROM $parent_image

# 1. 禁用交互式提示，防止 tzdata 等包在安装时卡死等待用户输入
ENV DEBIAN_FRONTEND=noninteractive

# 2. 维持你的代理环境变量

# 3. 增强 Apt 稳健性：开启下载重试 + 避免安装非必要依赖 + 清理缓存
# 如果使用代理拉取默认镜像源依然经常 502，可以在 apt-get update 前加一句换源命令：
# RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list || true; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Proxy "false";' \
      'Acquire::https::Proxy "false";' \
      > /etc/apt/apt.conf.d/80-retries; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        python3-setuptools \
        automake \
        cmake \
        git \
        flex \
        bison \
        libglib2.0-dev \
        libpixman-1-dev \
        cargo \
        libgtk-3-dev \
        ninja-build \
        gcc-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-plugin-dev \
        libstdc++-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-dev && \
    rm -rf /var/lib/apt/lists/*

# 4. 增强 Git 稳健性：增大缓存区应对大包解析错误，降低压缩率减轻 CPU 负担

# 5. 带重试机制的 Git Clone (最多尝试 3 次)，防止偶发的 early EOF
RUN for i in 1 2 3; do \
      git clone https://github.com/Kiciot/AFLplusplus /afl && break || \
      (echo "Clone failed, retrying in 5s..." && sleep 5); \
    done && \
    cd /afl && \
    git checkout e04c5739b4af4f03aac6ee99025bed4aad05c152

# 6. 编译构建
RUN cd /afl && \
    unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && \
    cp utils/aflpp_driver/libAFLDriver.a /
