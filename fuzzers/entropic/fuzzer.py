# 导入 FuzzBench 官方的 LibFuzzer 接口
from fuzzers.libfuzzer import fuzzer as libfuzzer_fuzzer

def build():
    """Build benchmark."""
    # 使用官方标准的 LibFuzzer 构建流程
    # 它会自动处理 -fsanitize=fuzzer, -fsanitize=address 等标志
    libfuzzer_fuzzer.build()

def fuzz(input_corpus, output_corpus, target_binary):
    """Run fuzzer."""
    # 直接调用 LibFuzzer 的运行逻辑，但是注入 entropic 参数
    # -entropic=1 : 开启 Entropic 能量调度
    libfuzzer_fuzzer.fuzz(
        input_corpus, 
        output_corpus, 
        target_binary, 
        flags=['-entropic=1']
    )