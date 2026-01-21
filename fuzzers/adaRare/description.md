# AFL++ with AdaRare Scheduling

## Fuzzer Name
AFL++ (AdaRare)

## Description
This fuzzer is a research variant of [AFL++](https://github.com/AFLplusplus/AFLplusplus) that implements a **lightweight adaptive scheduling and power allocation** framework.

## Core Features
- **Adaptive Power Scheduling**: Replaces the standard AFL++ schedule with a Multi-Armed Bandit (MAB) based approach (implemented via `adarare_bandit.c`).
- **Efficiency**: Designed to optimize seed selection and energy allocation dynamically to improve coverage convergence speed.
- **Implementation**: The logic is integrated directly into the AFL++ fuzzing loop, maintaining compatibility with standard AFL++ instrumentation.

## Research Context
This integration serves as a baseline for evaluating the effectiveness of adaptive scheduling strategies in Coverage-Guided Fuzzing (CGF). The source code is hosted at [https://github.com/Kiciot/AFLplusplus](https://github.com/Kiciot/AFLplusplus).