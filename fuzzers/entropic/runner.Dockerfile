# syntax=docker/dockerfile:1.6

# stage 1: builder image（由上一步已经 build 出来）
FROM gcr.io/fuzzbench/builders/entropic/${BENCHMARK}:latest AS builder

# stage 2: base runner（必须包含 fuzzbench 的 libfuzzer 运行脚本）
# 关键点：你这边 gcr.io/fuzzbench/runners/libfuzzer-runner:latest 不存在
# 通常写不带 tag，让它走默认 tag（很多仓库默认就是 latest，但你这里显式 latest 失败）
FROM gcr.io/fuzzbench/runners/libfuzzer-runner AS runner

COPY --from=builder /out /out