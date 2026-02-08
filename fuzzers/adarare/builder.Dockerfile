ARG parent_image
FROM $parent_image

# ==========================================
# 1. 代理与环境变量
# ==========================================
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

ENV AFL_SKIP_CPUFREQ=1
ENV AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1

# ==========================================
# 2. 安装依赖
# ==========================================
RUN apt-get update && \
    apt-get install -y \
        build-essential python3-dev python3-setuptools automake cmake git \
        flex bison libglib2.0-dev libpixman-1-dev cargo libgtk-3-dev \
        ninja-build \
        gcc-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-plugin-dev \
        libstdc++-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-dev \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# 3. 拉取 Adarare (AFL++ dev分支)
# ==========================================
RUN git config --global http.proxy http://172.17.0.1:7890

# 【关键修正】: 显式指定目录为 /afl
RUN git clone https://github.com/Kiciot/AFLplusplus /afl

# ==========================================
# 4. 编译构建
# ==========================================
WORKDIR /afl
RUN unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    # 使用 source-only 加速编译，除非你需要 QEMU
    PYTHON_INCLUDE=/ make source-only && \
    cp utils/aflpp_driver/libAFLDriver.a /

# 清理 git 配置
RUN git config --global --unset http.proxy