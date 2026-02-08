# 必须使用 libfuzzer-runner，因为它包含了处理 LibFuzzer 输出和覆盖率的脚本
FROM gcr.io/fuzzbench/runners/libfuzzer-runner