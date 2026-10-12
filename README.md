# TrueAlphaSpiral — TAS_DNA

**Human authority. Deterministic admissibility. Inspectable consequences.**

TAS_DNA brings the TrueAlphaSpiral collection into one public home: its purpose, state algebra, runtime code, schemas, tests, evidence, research, and public communication.

A model or program may propose an operation. The architectural goal is to admit consequential operations only under explicit authority and declared constraints, and to retain evidence for both admission and refusal. People and accountable institutions determine policy; cryptographic verification checks specified bindings and conditions.

## Start here

- [TAS_DNA collection index](TAS_DNA.md): the full map and reading paths.
- [TAS_DNA datum and state relation](docs/explainer/docs/tas-dna.md): origin, context, authority, operation, parent, invariants, decision, and receipt.
- [Claim manifest](IOC_CLAIM_MANIFEST.md): tested scope and deferred whole-system obligations.
- [Canonical workspace](WORKSPACE.md): imports, provenance, and remaining intake.
- [Curation contract](docs/curation/README.md) and [artifact register](docs/curation/artifacts.json): how evidence enters the collection.
- [Public campaign](docs/SDF_PUBLIC_CAMPAIGN.md): explain the work through receipts and reproducible checks.

## One state relation

```text
S_n = (O_n, Γ_n)
Γ_n = ordered evidence history of TAS_DNA genes
O_n = operational projection of admitted history

Admission: record the decision and authorized transition.
Refusal: preserve protected operational state and retain refusal evidence.
```

This is the architectural relation. The [formal state machine](docs/explainer/formal/state-machine.md) specifies it; implementations must be assessed at a named revision under their stated assumptions.

## Implementation and verification

Explore [core](core), [schemas](schemas), [tests](tests), and the [API reference](API_REFERENCE.md). The repository contains implementation and test material; this overview does not claim that all protected-state writers are mediated or that every receipt is authenticated.

The IOC manifest records narrow tested claims and open obligations including authenticated ancestry, durable atomic replay exclusion, authenticated receipts, crash consistency, and complete effect mediation. Conceptual and campaign documents should be read with those boundaries.

Local Python checks:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -q
```

These are reproduction instructions, not a report that tests were run for this documentation change.

## Current intake

The explainer snapshot is already present under [docs/explainer](docs/explainer). Other sources remain tracked in the [repository inventory](docs/migration/repository-inventory.md).

The Sovereign Data Claim [witness transition](docs/curation/witness-transition.md) and [energy evaluation](docs/curation/energy-evaluation.md) are proposed contracts. The calculator archive has a curator-reported digest but has not been recovered in this intake. No measured energy savings or new calculator seal is claimed.

The prior overview is preserved as [historical text](docs/curation/prior-readme.txt), with its source identity in the artifact register.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md). Submit a reproducible test vector with inputs, authority state, expected and observed verdicts, revision, and receipt checks. Preserve authorship, source history, license notices, and unresolved evidence gaps.

See [SECURITY.md](SECURITY.md) for security findings and existing source notices, including [LICENSE_RIDER.txt](LICENSE_RIDER.txt), for applicable terms.
