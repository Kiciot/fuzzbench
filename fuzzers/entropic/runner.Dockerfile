# syntax=docker/dockerfile:1.6
ARG parent_image

# 1) 先把 builder 产物当成一个 stage
FROM ${parent_image} as builder

# 2) runner 基础镜像：必须包含 libfuzzer 的运行脚本
FROM gcr.io/fuzzbench/runners/libfuzzer-runner:latest

# 3) 拷贝产物
COPY --from=builder /out /out