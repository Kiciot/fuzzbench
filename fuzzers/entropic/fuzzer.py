import os
import subprocess
from fuzzers.libfuzzer import fuzzer as libfuzzer_fuzzer

def build():
    libfuzzer_fuzzer.build()

def fuzz(input_corpus, output_corpus, target_binary):
    env = os.environ.copy()

    # FuzzBench 通常把 target 放在 /out/
    if os.path.isabs(target_binary):
        target_path = target_binary
    else:
        target_path = os.path.join("/out", target_binary)

    cmd = [
        target_path,
        "-entropic=1",
        # 推荐同时给工作 corpus(可写) + 种子 corpus(只读)
        output_corpus,
        input_corpus,
        # 可选：让崩溃/超时样本稳定落在 output_corpus 下，便于 runner 收集
        # f"-artifact_prefix={output_corpus}/",
    ]

    subprocess.check_call(cmd, env=env)