# 继承 FuzzBench 基础镜像
FROM gcr.io/fuzzbench/builders/benchmark-builder
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# 1. 安装 AFL++ 编译所需的依赖 (根据该仓库的 AFL++ 版本需求)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    automake \
    cmake \
    git \
    flex \
    bison \
    libglib2.0-dev \
    libpixman-1-dev \
    cargo \
    libgtk-3-dev \
    clang \
    llvm \
    llvm-dev \
    lld

# 2. 克隆包含 FunFuzz 的 Artifacts 仓库
# 注意：我们 Clone 整个仓库到 /funfuzz_repo
RUN git config --global http.proxy http://172.17.0.1:7890
RUN git config --global http.sslVerify false
RUN git clone https://github.com/funfuzz-tosem2023/funfuzz-artifacts.git /funfuzz_repo

# 3. 切换工作目录到子目录 aflpp-fun
WORKDIR /funfuzz_repo/aflpp-fun

# 4. 编译 Fuzzer
# 因为是基于 AFL++，使用 source-only 可以避免编译 QEMU/Unicorn，节省时间
RUN make source-only

# 5. 配置环境变量，供 fuzzer.py 使用
# 注意路径现在是 /funfuzz_repo/aflpp-fun
ENV CC="/funfuzz_repo/aflpp-fun/afl-clang-fast"
ENV CXX="/funfuzz_repo/aflpp-fun/afl-clang-fast++"
ENV AFL_PATH="/funfuzz_repo/aflpp-fun"
ENV FUZZER_LIB="/funfuzz_repo/aflpp-fun/afl-llvm-rt.o"