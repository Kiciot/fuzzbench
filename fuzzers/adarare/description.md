# AdaRare (Full)

AdaRare is a rarity-aware greybox fuzzing scheduler built on top of AFL++.
This variant evaluates the complete AdaRare design, including contextual
bandit scheduling, CmpLog reward feedback, and A6 off-policy weighting.

This FuzzBench integration pins AFL++ to the following AdaRare full commit:

- `72127243cef48d2551d8d02a8bb0aeb57055fc5d`

Key enabled components in this full variant include:

- Contextual/LinUCB-based arm selection
- Multi-objective reward shaping over coverage, rarity, throughput, and cmp progress
- Post-exec CmpLog reward feedback into the bandit
- A6 meta-arm with off-policy IPS/clipped-IPS weighting
- Dynamic dictionary scheduling and per-arm policy control

This variant is intended to serve as the reference implementation for
AdaRare ablation studies.