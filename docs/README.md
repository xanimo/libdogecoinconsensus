# docs/

`flattened_v1_spec.json` — the first extractor's output against real Core.

Kept as evidence, not as a reference. It **flattened Core's consensus fork
tree**: it reports `MAINNET.nPowTargetTimespan = 14400` and
`fDigishieldDifficultyCalculation = false` — the pre-Digishield values — and
silently discards the post-145000 regimes entirely.

A client generated from this spec would hard-fork itself off the network at
block 145,000.

It is here because it is the clearest possible illustration of the failure mode
this project exists to prevent: output that is confidently wrong. The extractor
did not lie about it — the tree wiring landed in `_unparsed` rather than
vanishing, which is what surfaced the bug. See DIRECTIVE.md §2a.
