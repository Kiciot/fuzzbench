from fuzzers import utils
import os

def build():
    """Build benchmark."""
    # 获取我们在 Dockerfile 中生成的静态库路径
    entropic_lib = os.environ.get('ENTROPIC_LIB', '/libEntropic.a')

    # 这里的 cflags 和 cxxflags 是关键：
    # 1. -fsanitize=fuzzer-no-link: 告诉 clang 进行覆盖率插桩，但不要链接系统自带的 libFuzzer
    # 2. -fsanitize=address: 通常配合 ASAN 使用
    cflags = ['-fsanitize=fuzzer-no-link', '-fsanitize=address']
    
    # 链接我们手动编译的 Entropic 库
    # 注意：某些 benchmark 需要 -lstdc++，libFuzzer 通常是用 C++ 写
    cxxflags = cflags + [entropic_lib, '-lstdc++']

    utils.build_benchmark(
        fuzzer_name_or_path='entropic',
        sanitizers=['address'], # FuzzBench 会自动处理 sanitizer，但我们需要自定义 flag 覆盖
        extra_cflags=cflags,
        extra_cxxflags=cxxflags
    )
