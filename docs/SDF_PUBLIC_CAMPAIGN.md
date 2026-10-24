# Sovereign Data Foundation Public Campaign

## Campaign platform: **Show the Receipt**

**Public promise:** Before an automated system can affect a person, it should be
able to show what it was allowed to do, which rules it checked, what evidence it
used, and why the action was accepted or refused.

This campaign should not ask the public to replace faith in one black box with
faith in another. It should invite people to inspect a narrower, testable
proposition: consequential automated actions need explicit authority,
pre-declared constraints, and independently verifiable records.

## 1. Message hierarchy

### Lead with the civic problem

Automated decisions increasingly affect benefits, employment, housing,
healthcare, education, and public services. A plausible answer is not the same
thing as an authorized action, and an explanation generated after the fact is
not the same thing as evidence that safeguards ran beforehand.

### Introduce the standard in plain language

Use one public-facing rule:

> **No authority, no action. No proof, no trust.**

Describe Sovereign Intelligence as a governance pattern around computational
systems—not as a sentient replacement for AI. A probabilistic model may propose
an answer or action. A separate deterministic control layer decides whether it
may proceed under explicit rules and produces a receipt for that decision.

### Make the receipt concrete

Every receipt should let an auditor answer:

1. **Origin:** What system and inputs produced the proposal?
2. **Authority:** Which authenticated capability permitted this action?
3. **Rules:** Which versioned invariants were evaluated?
4. **Result:** Was the action admitted or refused, and why?
5. **Continuity:** Does the record link to an unbroken, tamper-evident history?
6. **Impact:** What state changed—or, on refusal, what state demonstrably did
   not change?

### End with public control

Frame the benefit as **digital due process**: rules declared before action,
consistent checks, meaningful refusal, appeal paths, and evidence available to
independent auditors. The goal is not to claim that mathematics chooses public
values. People and legitimate institutions set policy; verification tests
whether a system obeyed that policy.

## 2. Three campaign pillars

### Authority before action

Systems should possess only narrowly scoped, authenticated capabilities.
Neither fluent output nor operator convenience grants permission.

**Proof point to demonstrate:** Attempt an action with a valid capability, then
repeat it with an absent, expired, or revoked capability and publish both
receipts.

### Evidence before assertion

High-impact claims should identify their sources, rule set, software version,
and verification result. Cryptographic integrity can show that a record was not
altered; it cannot, by itself, prove that an input is true or a policy is just.

**Proof point to demonstrate:** Give independent reviewers a receipt, public
verification instructions, and the referenced artifact so they can reproduce
the check.

### Refusal without side effects

A safe refusal is an observable system outcome, not a conversational apology.
An inadmissible request should fail closed, record the reason, and leave
protected operational state unchanged.

**Proof point to demonstrate:** Publish before-and-after state commitments for a
blocked action, plus the refusal receipt and replay procedure.

## 3. Audience ladder

| Audience | Start with | Evidence to offer | Call to action |
|---|---|---|---|
| General public | “You deserve a receipt when automation affects your life.” | A human-readable sample receipt and a 60-second verification demo | Ask institutions to adopt the Public Receipt Pledge |
| Public servants | “Turn policy obligations into testable pre-action checks.” | A sandbox pilot, failure scenarios, and accessibility/appeal workflow | Nominate one bounded workflow for evaluation |
| Engineers | “Separate generation, authority, verification, and actuation.” | Threat model, schemas, tests, deterministic replay, and key-management design | Run the verifier and file reproducible findings |
| Auditors and researchers | “Do not trust our interpretation; reproduce it.” | Versioned artifacts, limitations, test vectors, and independent reports | Attempt to falsify a published claim |
| Civil-society groups | “Digital due process must preserve human rights and recourse.” | Impact assessment, governance roles, retention rules, and incident process | Co-design requirements and redress criteria |

## 4. Campaign sequence

### Phase 1 — The contrast: plausible is not proven

Use side-by-side examples rather than attacks on all AI or RLHF. Show a fluent
response beside a receipt-bearing decision. Ask: *Which one can you audit?*
Avoid saying probabilistic models merely “roll dice”; explain that their outputs
are statistically generated and may be useful, while remaining insufficient as
proof of authority or correctness.

### Phase 2 — The mechanism: proposal, gate, receipt

Use a repeatable three-frame visual:

1. **Proposal:** A model or conventional program requests an action.
2. **Gate:** Explicit authority and invariants are checked.
3. **Receipt:** A refusal receipt is recorded without a protected-state transition;
   an admission receipt records the resulting transition and its before-and-after
   state commitments.

Reserve architecture-specific names such as Living Braid, SentientLock, and
Gold/Teal/Violet threads for technical material. In public copy, pair every name
with an operational definition and a link to executable evidence.

### Phase 3 — The public proof

Launch a small, bounded challenge with published success criteria. Include at
least one allowed case, one unauthorized case, one malformed-input case, and one
revoked-authority case. Publish commands, expected outputs, software versions,
and known limitations. Invite independent reproduction and record failures as
open issues rather than hiding them.

### Phase 4 — The pledge

Ask organizations to commit to five requirements:

1. publish the authority model and versioned rules;
2. verify before high-impact actuation;
3. issue receipts for admissions and refusals;
4. provide independent audit and human appeal;
5. disclose limitations, incidents, and changes.

The pledge should have measurable conformance criteria and must not imply
certification until an independent assessment process exists.

## 5. Claim discipline

All campaign claims should carry one of these labels:

- **Implemented:** linked to code, tests, and a reproducible demonstration in a
  named release.
- **Validated:** reproduced by an identified independent party under a published
  protocol.
- **Proposed:** specified but not yet demonstrated.
- **Aspirational:** a desired social or technical outcome, not a current fact.

Do not use **proven**, **guaranteed**, **immutable**, **unalterable**, or
**eliminates hallucinations** without a defined threat model and evidence that
supports that exact scope. Prefer **tamper-evident** to *tamper-proof* and
**deterministically enforces the encoded rule** to *proves truth*. Shannon
entropy, the golden ratio, hashes, signatures, and Merkle structures each have
specific properties; none should be presented as a general measure of semantic
truth, safety, justice, or intelligence.

## 6. Ready-to-use copy

### Campaign headline

> **If automation can affect your life, it should show its receipt.**

### Campaign subhead

The Sovereign Data Foundation is advancing a public standard for authority,
pre-action verification, auditable refusal, and human appeal—so consequential
automation can be inspected rather than merely trusted.

### 30-second message

> Today’s AI can produce convincing answers without proving that they are true
> or that an action is authorized. We believe consequential systems need a
> higher standard. Before an automated action affects a person, it should check
> explicit rules and scoped authority, then produce a verifiable receipt showing
> what happened. If the proof is missing, the action stops. That is digital due
> process: rules before action, evidence after it, and a path for human appeal.

### Short social copy

**Fluency is not authority. Explanation is not evidence. If automation can
affect your life, demand the receipt.**

### Public call to action

> Review the rules. Run the test. Verify the receipt. Challenge the claim.

## 7. Public demo acceptance criteria

A campaign demonstration is ready only when:

- a clean environment can reproduce it from documented commands;
- accepted and refused cases use the same published verification path;
- a refusal does not mutate protected state;
- receipts use a documented, versioned schema;
- signature and chain verification fail on deliberate tampering;
- policy authorship is distinguishable from mechanical policy enforcement;
- key custody, revocation, replay, privacy, and retention assumptions are stated;
- accessibility and human appeal are demonstrated, not merely promised; and
- known gaps and non-goals appear beside the demo, not in fine print.

## 8. Recommended launch assets

1. A one-page **Receipt Bill of Rights** for the public.
2. An interactive **Proposal → Gate → Receipt** demonstration.
3. A public receipt explorer with redacted sample data.
4. A technical verification guide and machine-readable schemas.
5. A threat model, privacy assessment, and key-management explainer.
6. An independent red-team report with unresolved findings.
7. A pilot toolkit for agencies and community oversight groups.

The strongest campaign posture is confident but falsifiable: **do not ask
America whether it is ready to believe. Ask everyone to verify.**
