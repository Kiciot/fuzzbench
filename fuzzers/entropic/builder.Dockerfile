FROM gcr.io/fuzzbench/builders/benchmark-builder

ARG PROXY=http://172.17.0.1:7890
ENV HTTP_PROXY=${PROXY} HTTPS_PROXY=${PROXY} http_proxy=${PROXY} https_proxy=${PROXY} \
    NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16 no_proxy=localhost,127.0.0.1,::1,172.17.0.0/16

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git curl \
 && rm -rf /var/lib/apt/lists/*

RUN git config --global http.proxy ${PROXY} \
 && git config --global https.proxy ${PROXY}

# --- Fetch llvm-project by commit (avoid full clone) ---
WORKDIR /
RUN git init llvm-project \
 && cd llvm-project \
 && git remote add origin https://github.com/llvm/llvm-project.git \
 && git fetch --depth 1 origin 29cc50e17a6800ca75cd23ed85ae1ddf3e3dcc14 \
 && git checkout FETCH_HEAD

# --- Build Entropic libFuzzer engine ---
WORKDIR /llvm-project/compiler-rt/lib/fuzzer
RUN clang++ -O2 -std=c++11 -fPIC -c *.cpp \
 && ar rcs /libEntropicEngine.a *.o \
 && ranlib /libEntropicEngine.a

ENV ENTROPIC_ENGINE=/libEntropicEngine.a
WORKDIR /src