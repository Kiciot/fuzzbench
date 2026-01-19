# 继承自标准的 AFL Runner (因为它包含了启动 afl-fuzz 所需的脚本和环境)
FROM gcr.io/fuzzbench/runners/afl-runner

# 将构建阶段的整个 aflpp-fun 目录拷贝到运行时镜像的 /funfuzz 目录
# 注意：我们这里重命名为 /funfuzz 方便管理
COPY --from=builder /funfuzz_repo/aflpp-fun /funfuzz

# 设置环境变量
ENV PATH="/funfuzz:${PATH}"
ENV AFL_PATH="/funfuzz"

# (可选) 确保 afl-fuzz 可执行
RUN chmod +x /funfuzz/afl-fuzz