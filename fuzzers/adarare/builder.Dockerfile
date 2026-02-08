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
# 3. 拉取并编译 Adarare (一步完成)
# ==========================================
# 核心修改：
# 1. 不使用 WORKDIR /afl (避免改变全局状态)
# 2. 使用 cd /afl && ... 在子 shell 中执行
# 3. 编译完成后清理代理设置
RUN git config --global http.proxy http://172.17.0.1:7890 && \
    git clone https://github.com/Kiciot/AFLplusplus /afl && \
    cd /afl && \
    unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make source-only && \
    cp utils/aflpp_driver/libAFLDriver.a / && \
    git config --global --unset http.proxy