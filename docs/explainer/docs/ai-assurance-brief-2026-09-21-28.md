# AI Assurance Brief — September 21–28, 2026

The strongest development for TAS in this window is the appearance of infrastructure intended to enforce agent permissions outside the model. Independent proof checking also advanced. Standards activity remains important but is still mostly proposals and drafts rather than deployed constitutional machinery.

## 1. NVIDIA Open Agent Safety Platform — evaluate

NVIDIA announced OpenShell software availability alongside Sentry, a reference design for independent monitoring and enforcement on BlueField-4 hardware, and reported more than 100 participating organizations. That is a meaningful ecosystem signal, but not independent evidence of deployment effectiveness or constitutional sufficiency.

Source: [NVIDIA, "NVIDIA Launches Open Agent Safety Platform to Protect Agentic AI Systems"](https://nvidianews.nvidia.com/news/open-agent-safety-platform?utm_source=chatgpt.com)

### TAS implication

OpenShell is worth evaluating as a possible enforcement component at the execution boundary.

TAS should require tests showing that:

- denied operations cannot reach protected resources,
- direct bypass attempts fail closed,
- policy changes cannot self-authorize around the gate.

Runtime containment alone does not establish human-rooted authority, admissibility, or durable admission receipts.

## 2. Independent proof reconstruction in Leo-III / Dedukti — evaluate experimentally

Researchers integrated Dedukti proof reconstruction into Leo-III. Their prototype reconstructs approximately 80% of generated proof steps and uncovered bugs in Leo-III. This is a research-stage result. The reported percentage applies to proof steps, not to complete independently verified systems.

Source: [arXiv: "Independent Verification of Leo-III's Reasoning via Dedukti"](https://arxiv.org/abs/2609.24594?utm_source=chatgpt.com)

### TAS implication

This supports a TAS design principle directly: proof generation and proof acceptance should remain separate.

A useful near-term experiment is to export one small invariant proof for independent checking and treat unsupported reconstruction as unresolved rather than silently accepted.

## 3. Post-quantum EAP-TLS draft — watch and test interoperability

The IETF draft `draft-ietf-emu-pqc-eap-tls-02` addresses post-quantum protection for TLS-based EAP methods and highlights operational issues caused by larger certificate chains. It specifies advance retrieval of intermediate certificates to reduce handshake size. It remains an Internet-Draft, not a finalized RFC.

Source: [IETF Internet-Draft: "Post-quantum Cryptography for EAP-TLS"](https://datatracker.ietf.org/doc/html/draft-ietf-emu-pqc-eap-tls-02?utm_source=chatgpt.com)

### TAS implication

For deployments that rely on EAP, evaluate:

- certificate-chain size,
- fragmentation behavior,
- onboarding and rotation paths,
- interoperability impact.

Transport protection and receipt-signature migration should remain separate engineering workstreams.

## 4. Coordinated frontier-AI standards proposal — watch

OpenAI proposed coordinated frontier-AI standards around common capability measurements, human-review triggers, and incident classification/reporting through national and international institutions. This is a policy proposal, not an adopted technical standard or executable verification mechanism.

Source: [OpenAI, "Building standards for the next phase of AI"](https://openai.com/index/building-standards-next-phase-ai/?utm_source=chatgpt.com)

### TAS implication

TAS should keep evidence exportable without making reporting systems authoritative. Receipts should bind:

- policy version,
- authorization context,
- outcome,
- execution identity.

That allows future reporting requirements to consume evidence without controlling the gate itself.

## Coverage limits

This brief does not establish that no important zero-knowledge tooling release or standalone cryptographic-provenance release occurred in the same window. Some release pages were inaccessible, so absence here is not evidence of absence.

## Recommended next engineering step

Use the existing [Technical Companion](https://docs.google.com/document/d/1GNmuuyvPa3NUNDGk37Nwav6I891J6hyhzFrj3rPvmIU/edit) to define a small OpenShell compatibility test with:

- one allowed operation,
- one denied operation,
- one direct bypass attempt,
- one unauthorized policy-change attempt.

Record actual effects and authenticated evidence separately. The purpose is to test whether the infrastructure can support the TAS boundary before considering adoption.
