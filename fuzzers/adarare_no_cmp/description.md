# AdaRare (No Cmp Reward)

AdaRare is a rarity-aware greybox fuzzing scheduler built on top of AFL++.
This ablation variant disables CmpLog-derived reward feedback into the
bandit scheduler while preserving the rest of the AdaRare system.

This FuzzBench integration pins AFL++ to the following AdaRare no-cmp commit:

- `b4edae3bb73849d3ada60faead85392e1fd0415a`

Ablation intent:

- Remove cmp-progress reward injection into AdaRare's reward pipeline
- Keep the remaining AdaRare mechanisms active, including:
  - contextual/LinUCB scheduling
  - rarity- and coverage-aware reward shaping
  - A6 meta-arm and off-policy weighting
  - standard cmplog/redqueen execution paths

This variant is designed to isolate the contribution of continuous cmp-based
reward feedback, without turning off AFL++'s underlying cmplog-related
execution support itself.