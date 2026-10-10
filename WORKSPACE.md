# TAS canonical workspace

This repository, [Sovereign-Data-Foundation/TrueAlpha-spiral](https://github.com/Sovereign-Data-Foundation/TrueAlpha-spiral), is the chosen home for active TAS specifications, code, fixtures, and verification evidence. This document records consolidation status; a link or an imported document is not evidence that its implementation has been verified.

## Where to find the work

| Area | Canonical location | Status |
| --- | --- | --- |
| Runtime admission, WakeChain, receipts, schemas, tests | [Core repository](./README.md), [core](./core), [schemas](./schemas), [tests](./tests) | Existing mainline implementation; individual claims require their own tests and revision |
| TAS_DNA and cursive computation explainer | [Imported explainer](./docs/explainer/README.md) | Source snapshot copied byte for byte into this branch; proposed for mainline review |
| Formal state machine and terminology | [Formal](./docs/explainer/formal/state-machine.md), [terminology](./docs/explainer/spec/terminology.md) | Source snapshot; specification, not runtime proof |
| Public overview and claim boundaries | [README](./README.md), [IOC claim manifest](./IOC_CLAIM_MANIFEST.md), [public campaign](./docs/SDF_PUBLIC_CAMPAIGN.md) | Existing content; claim status is defined in each document |

## Import provenance

The 15 text files under `docs/explainer/` are an unchanged path-preserving copy of [Sovereign-Data-Foundation/truealpha-spiral-explainer at ce1f567b0cb7672876df5ee48ff4c0e1c3d54236](https://github.com/Sovereign-Data-Foundation/truealpha-spiral-explainer/tree/ce1f567b0cb7672876df5ee48ff4c0e1c3d54236), including its LICENSE. Their Git blob SHA-1 objects match the source tree. The source repository remains available with its own commits, issues, and pull requests. This import records a source snapshot; it does not transfer Git history, tests, or issue discussion into this repository.

## Remaining intake

| Source | Disposition before import |
| --- | --- |
| [TrueAlpha-spiral/TrueAlpha-spiral](https://github.com/TrueAlpha-spiral/TrueAlpha-spiral) | Parent of this repository's fork. Compare divergent branches and reconcile original work by reviewed PR, preserving author, source commit, and conflicting implementation decisions. Do not replace this branch with a bulk copy. |
| [Sovereign-Data-Foundation/TASHUMANSIG001-1-](https://github.com/Sovereign-Data-Foundation/TASHUMANSIG001-1-) and [truealphaspiral-ethent](https://github.com/Sovereign-Data-Foundation/truealphaspiral-ethent) | Review distinct gateway, witness, tests, and release material; import only nonduplicated components with source commit and runnable checks. |
| [Sovereign-Data-Foundation/3a7bd3e2360f7c3b7436f8d7c1b92eb4e3e53d54a17d3f5eae17eb4a69b1f04d-truealpha-spiral.py](https://github.com/Sovereign-Data-Foundation/3a7bd3e2360f7c3b7436f8d7c1b92eb4e3e53d54a17d3f5eae17eb4a69b1f04d-truealpha-spiral.py) | Review the pilot branch and its personal fork for unique code and branch-only evidence. |
| [TrueAlpha-spiral/sealed](https://github.com/TrueAlpha-spiral/sealed) | Preserve as a historical source; check claims against reproducible artifacts before calling them verified here. |
| Tool and documentation forks | OpenClaw, Gemini CLI, Pinata docs, Conductor, and other upstream forks remain linked dependencies or experiments. Import TAS-specific changes only after attribution and license review; do not copy upstream repositories wholesale. |
| Private repositories and off-GitHub artifacts | Excluded from this public import. Review visibility, ownership, secrets, and publication rights separately before any transfer. |

A single canonical workspace means new TAS work lands here by default. It does not require deleting older repositories or erasing their independent histories. A future migration can mark a source read-only after its unique work and references are accounted for.

## Intake record for each later change

Record: source repository and commit; original path and blob digest; destination path and commit; author/license; whether it is a draft, specification, code, test added, or test actually run; and any superseded or mirrored copy. Protected actions still require the repository's existing review and verification gates.
