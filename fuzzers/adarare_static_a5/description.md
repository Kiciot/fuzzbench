# AdaRare Static A5

Profile-control AdaRare FuzzBench variant.

- FuzzBench variant: `adarare_static_a5`
- AFL++ repo: `https://github.com/Kiciot/AFLplusplus`
- AFL++ pinned commit: `e04c5739b4af4f03aac6ee99025bed4aad05c152`
- Experiment group: `profile-control`
- A6 delegated sharing: disabled by profile-control policy
- Window: `AFL_BANDIT_WINDOW_MS=5000`

Runtime environment:

```text
AFL_ADARARE_POLICY=static_profile
AFL_ADARARE_STATIC_ARM=5
```
