import os
import subprocess
from fuzzers.libfuzzer import fuzzer as libfuzzer_fuzzer

def build():
    libfuzzer_fuzzer.build()

def fuzz(input_corpus, output_corpus, target_binary):
    # libFuzzer 约定：第一个 corpus 目录是“写回”的输出 corpus
    # FuzzBench 传进来的 output_corpus 正好满足这个语义
    cmd = [
        target_binary,
        '-entropic=1',
        output_corpus,
        input_corpus,
    ]
    subprocess.check_call(cmd, env=os.environ.copy())