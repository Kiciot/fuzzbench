# AdaRare (No Context)

AdaRare is a rarity-aware greybox fuzzing scheduler built on top of AFL++.
This ablation variant disables the contextual/LinUCB scheduling component
while keeping the rest of the AdaRare system intact.

This FuzzBench integration pins AFL++ to the following AdaRare no-context commit:

- `fee6f2d0368a7b505d892368f4980ff4e6a5cd45`

Ablation intent:

- Remove contextual feature-driven LinUCB scheduling
- Preserve the remaining AdaRare mechanisms, including:
  - reward shaping
  - CmpLog reward feedback
  - A6 meta-arm logic
  - dictionary-related policy control

Operationally, this variant is intended to approximate a non-contextual
bandit baseline within the AdaRare framework, so that the contribution of
context-aware scheduling can be isolated in FuzzBench experiments.