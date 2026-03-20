# AdaRare (No IPS Weighting)

AdaRare is a rarity-aware greybox fuzzing scheduler built on top of AFL++.
This ablation variant disables the inverse propensity scoring (IPS /
clipped-IPS) weighting used by the A6 meta-arm, while keeping the rest of
the AdaRare system intact.

This FuzzBench integration pins AFL++ to the following AdaRare no-IPS commit:

- `560f635991e66781126d1323edbba5db802f814c`

Ablation intent:

- Remove IPS-based off-policy weighting from A6 updates
- Preserve the remaining AdaRare mechanisms, including:
  - contextual/LinUCB scheduling
  - reward shaping
  - cmp-reward feedback
  - A6 delegation/meta-arm behavior itself

This variant is intended to isolate the effect of off-policy importance
weighting in AdaRare's hierarchical A6 arm, without removing the A6 arm
as a scheduling mechanism.