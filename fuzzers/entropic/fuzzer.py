from fuzzers import utils
import os

def build():
    entropic_engine = os.environ.get("ENTROPIC_ENGINE", "/libEntropicEngine.a")

    # 编译期：插桩但不链接系统 libFuzzer
    cflags = ["-fsanitize=fuzzer-no-link", "-fsanitize=address"]
    cxxflags = ["-fsanitize=fuzzer-no-link", "-fsanitize=address"]

    # 关键：链接期引擎
    os.environ["LIB_FUZZING_ENGINE"] = entropic_engine

    utils.build_benchmark(
        # 这里的 fuzzer_name_or_path 仍然写 entropic（只要你在 fuzzers/entropic 目录下）
        # 或者你也可以写一个已存在的名字，但不建议混用。
        fuzzer_name_or_path="entropic",
        sanitizers=["address"],
        extra_cflags=cflags,
        extra_cxxflags=cxxflags,
    )