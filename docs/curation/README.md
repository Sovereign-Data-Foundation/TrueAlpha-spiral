# TAS_DNA curation contract

This repository is the public home for the TAS_DNA collection. [The index](../../TAS_DNA.md) connects purpose, architecture, specifications, implementation, evaluation, public communication, and history. [The workspace ledger](../../WORKSPACE.md) identifies the canonical repository and existing imports.

## Every intake preserves four answers

1. What was intended?
2. What was produced?
3. What was demonstrated, by whom, with which commands and inputs?
4. Where are the source and destination now?

Record source repository or artifact, immutable revision, original path, digest algorithm and value, authorship, license or publication permission, destination, relationships, and evidence scope. Use null for unknown values. Never invent a seal from a version label.

## Separate content status from verification status

Content may be purpose, specification, implementation, test, measurement, campaign, or history. Verification may be unverified, curator-reported, reproduced, or machine-proved. A source can contain executable code while its guarantees remain unverified.

Existing vocabulary remains authoritative within its scope: the IOC manifest distinguishes DESIGNED, TESTED, and PROVED; the public campaign distinguishes Proposed, Implemented, Validated, and Aspirational. Do not automatically promote one label into another. Machine-proved claims require identified theorem, assumptions, proof checker, and result; reproduced claims require actual run evidence.

## Import and reconcile

Compare source commits before importing. Preserve attribution and license terms. Keep unchanged snapshots separate from edited derivatives. Record mirrors and supersession explicitly, and resolve divergent behavior through reviewed changes. Tool forks stay external unless a TAS-specific component is identified.

A public repository should contain material cleared for publication. Keep credentials, signing keys, personal records, and undisclosed private source outside it. The collection does not require changing source-repository visibility.

## Evidence and sealing

A release manifest binds actual code, configuration, specification, fixtures, expected outputs, and reproduction instructions to digests. Record signing key identity and trust assumptions separately from content hashes. A successful test establishes its tested scope, not whole-system complete mediation or legal compliance.

The calculator archive in [artifacts.json](artifacts.json) is a recovery target with a curator-reported digest. It is not recovered or independently reproduced by this change. A reconstruction must receive a new identity and retain its relationship to the missing original.

## Intake order

Recover the calculator archive; reconcile parent/core divergence; compare unique witness and gateway modules; inventory branch-only pilot evidence; then incorporate cleared off-GitHub documents. See the [existing source inventory](../migration/repository-inventory.md) for repository-level disposition.

## Maintenance

Keep the index and artifact register current in the same pull request as an intake. If a claim is corrected, preserve the prior record and explain the supersession. Record failures and missing artifacts visibly. Public summaries should point to narrow evidence and its limitations.
