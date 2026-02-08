import os
# 直接继承官方 AFL++ 的逻辑
from fuzzers.aflplusplus import fuzzer as aflplusplus_fuzzer

def build():
    """Build benchmark."""
    # 复用 AFL++ 标准构建流程
    aflplusplus_fuzzer.build()

def fuzz(input_corpus, output_corpus, target_binary):
    """Run fuzzer."""
    
    # ======================================================
    # 【配置区域】Adarare Bandit 参数微调
    # 你可以在这里通过环境变量控制你的 "自动挡跑车"
    # ======================================================
    
    # 强制开启 Bandit 模式 (如果你的代码需要环境变量开关)
    # os.environ['AFL_ADARARE_ENABLE'] = '1'
    
    # 设置时间窗口 (例如 1000ms)
    # os.environ['AFL_ADARARE_WINDOW_MS'] = '1000'
    
    # 开启调试日志 (这样你可以在 logs 里看到 CSV 输出)
    # os.environ['AFL_DEBUG'] = '1' 

    # ======================================================

    # 获取默认运行参数
    run_options = aflplusplus_fuzzer.get_run_options(
        input_corpus, output_corpus, target_binary)

    # 启动 Fuzzer
    aflplusplus_fuzzer.fuzz_with_options(run_options)