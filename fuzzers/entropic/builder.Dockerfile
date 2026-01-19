# 继承自标准构建器
FROM gcr.io/fuzzbench/builders/benchmark-builder
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY
RUN git config --global http.proxy http://172.17.0.1:7890
RUN git config --global http.sslVerify false

# 1. 检出 Entropic 对应的 LLVM 代码 (对应你脚本中的 git clone)
RUN git clone https://github.com/llvm/llvm-project.git /llvm-project
WORKDIR /llvm-project
# 切换到 Entropic 的特定 commit
RUN git checkout 29cc50e17a6800ca75cd23ed85ae1ddf3e3dcc14

# 2. 手动编译 libFuzzer.a (对应你脚本中的编译循环)
# 我们直接在 Docker 构建阶段完成这个库的编译
WORKDIR /llvm-project/compiler-rt/lib/fuzzer
RUN clang++ -stdlib=libstdc++ -fPIC -O2 -std=c++11 *.cpp -c && \
    ar r /libEntropic.a *.o

# 3. 编译 driver.o (虽然通常 libFuzzer.a 自带 main，但为了保险起见按照你的脚本生成)
RUN clang++ -stdlib=libstdc++ -fPIC -O2 -std=c++11 -c driver.cpp -o /driver.o

# 4. 设置环境变量，方便 fuzzer.py 找到它们
ENV ENTROPIC_LIB="/libEntropic.a"
ENV ENTROPIC_DRIVER="/driver.o"

# 恢复工作目录
WORKDIR /src
