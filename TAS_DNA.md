# TAS_DNA: public collection index

TAS_DNA is the organizing thread for this public collection: human authority, admissible operations, authenticated lineage, refusal, and recovery. The canonical home is [Sovereign-Data-Foundation/TrueAlpha-spiral](https://github.com/Sovereign-Data-Foundation/TrueAlpha-spiral).

At the architectural level, a gene carries origin, context, authority, operation, parent, invariants, decision, and receipt. The full state is S = (O, Γ): operational state plus evidence history. A refusal preserves protected operational state while recording the attempted decision. See the [datum formalization](docs/explainer/docs/tas-dna.md) for the distinction between the full history and admitted projection.

## Navigate the collection

| Collection | Where to start | What it contains |
| --- | --- | --- |
| Purpose and human agency | [Foundational axioms](docs/explainer/docs/foundational-axioms.md), [constitutional layer](docs/explainer/docs/constitutional-meta-layer.md), [manifesto](manifesto) | Purpose, policy authority, civic interpretation; social goals are not implementation evidence |
| Architecture and TAS_DNA | [Explainer](docs/explainer/README.md), [recursive context](docs/explainer/docs/the_tas_recursive_contextualization.md), [architecture](docs/architecture) | State relations, perspective, recursive composition, cursive computation |
| Formal contracts | [State machine](docs/explainer/formal/state-machine.md), [terminology](docs/explainer/spec/terminology.md), [specifications](docs/specs), [schemas](schemas) | Definitions and machine-facing formats |
| Runtime and interfaces | [Core](core), [API reference](API_REFERENCE.md), [admission boundary](tas_admissibility.py), [evidence envelope](sdf_evidence_envelope.py) | Existing code; capabilities must be assessed at a named revision |
| Sovereign data claims | [Witness transition draft](docs/curation/witness-transition.md) | Proposed claimant, witness, challenge, atomicity, and refusal obligations |
| Verification and evaluation | [Tests](tests), [conformance tests](conformance-tests), [claim manifest](IOC_CLAIM_MANIFEST.md), [energy protocol](docs/curation/energy-evaluation.md) | Checks, limitations, and proposed measurement protocol |
| Receipts and release evidence | [Ledger](ledger), [attestations](ATTESTATIONS), [audits](audits), [artifact register](docs/curation/artifacts.json) | Evidence locations and explicit recovery gaps |
| Public communication | [SDF campaign](docs/SDF_PUBLIC_CAMPAIGN.md), [deck](TAS_DNA_Deck.md), [singularity context](TrueAlpha-singularity.md) | Campaign and conceptual material; consult claim boundaries before reuse |
| Research and experiments | [Pythonetics](tas_pythonetics), [recursion conversion](tas-recursion-conversion), [TAS stack](tas-stack), [TAS0x](tas0x), [Wolfram](wolfram) | Experimental branches of the collection; listing is not validation |
| Publication material | [DOI package](tas_dna_doi_package_v0.1), [citation](citation.bib), [metadata](zenodo_metadata.json) | Publication preparation; identifiers and releases require independent confirmation |
| Historical sources and tool forks | [Repository inventory](docs/migration/repository-inventory.md), [workspace ledger](WORKSPACE.md) | Source relationships, import provenance, and remaining intake |

## Read according to your purpose

Public readers: begin with the campaign and foundational axioms.
Engineers: read the state machine, API reference, claim manifest, and named tests.
Curators: use the [curation contract](docs/curation/README.md) and [contribution guide](CONTRIBUTING.md).
Auditors: start with the artifact register; request the exact inputs, revision, commands, and expected results for a claim.

## Coverage and continuity

This index covers the repository areas inspected on 2026-10-11 and the topics developed in the curator's conversation. It is not a claim that every historical, private, or off-GitHub artifact has been recovered. Preserve those gaps in the artifact register and source inventory.

The existing explainer import is preserved. Unique code in other repositories still needs revision-level comparison and intake. Older originals retain their histories; an index entry does not supersede them.

The prior root overview is preserved unchanged as [historical text](docs/curation/prior-readme.txt). Its source revision and blob identity are recorded in the artifact register. Its relative references should be read at the source revision, and its claims do not acquire verified status through preservation.
