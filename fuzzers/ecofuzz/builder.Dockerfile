# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' \
      "${HTTP_PROXY}" "${HTTPS_PROXY:-$HTTP_PROXY}" > /etc/apt/apt.conf.d/99proxy; \
  fi && \
  printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    > /etc/apt/apt.conf.d/80-retries

RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY:-$HTTP_PROXY}"; \
  fi

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      make \
      clang \
      llvm \
      binutils \
      libc++-dev \
      libc++abi-dev && \
    rm -rf /var/lib/apt/lists/*


ARG ECOFUZZ_REPO="https://github.com/MoonLight-SteinsGate/EcoFuzz"

RUN \
  for i in {1..5}; do \
    git clone --no-tags --filter=blob:none "${ECOFUZZ_REPO}" /EcoFuzz && break || (rm -rf /EcoFuzz && sleep $((i*2))); \
  done && \
  if [[ -n "${ECOFUZZ_COMMIT}" ]]; then \
    cd /EcoFuzz && git checkout "${ECOFUZZ_COMMIT}"; \
  fi && \
  mv /EcoFuzz/EcoFuzz /afl && \
  cd /afl && \
  AFL_NO_X86=1 make

ARG LLVM_COMMIT="5feb80e748924606531ba28c97fe65145c65372e"
RUN \
  url="https://raw.githubusercontent.com/llvm/llvm-project/${LLVM_COMMIT}/compiler-rt/lib/fuzzer/afl/afl_driver.cpp"; \
  for i in {1..5}; do \
    wget -t 5 -T 30 -O /afl/afl_driver.cpp "${url}" && break || sleep $((i*2)); \
  done && \
  test -s /afl/afl_driver.cpp && \
  clang -Wno-pointer-sign -c /afl/llvm_mode/afl-llvm-rt.o.c -I/afl && \
  clang++ -stdlib=libc++ -std=c++11 -O2 -c /afl/afl_driver.cpp && \
  ar r /libAFL.a *.o