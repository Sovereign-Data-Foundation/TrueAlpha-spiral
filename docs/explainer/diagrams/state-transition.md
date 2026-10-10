# TAS_DNA State Relation

```mermaid
flowchart TD
    P[Proposal / Instruction] --> V[Verification / Admissibility]
    V -->|Admitted| GA[TASGene<br/>decision = ADMITTED]
    V -->|Refused| GR[TASGene<br/>decision = REFUSED]
    V -->|Cannot safely represent normal decision| F[Fail-stop]

    GA --> G[Authenticated lineage Gamma]
    GR --> G

    G --> A[Admitted projection Pi_A Gamma]
    A --> O[Operational state O]
    G --> S[Full state S = O, Gamma]
    O --> S
```

## Admission

```mermaid
flowchart LR
    G1[TAS_DNA gene: ADMITTED] --> L1[Gamma extends]
    G1 --> A1[Admitted projection extends]
    A1 --> O1[Operational state may advance]
    L1 --> S1[Full state advances]
    O1 --> S1
```

## Refusal

```mermaid
flowchart LR
    G2[TAS_DNA gene: REFUSED] --> L2[Gamma extends]
    G2 --> A2[Admitted projection unchanged]
    A2 --> O2[Operational state unchanged]
    L2 --> S2[Full state advances]
    O2 --> S2
```

The refusal branch therefore satisfies both:

\[
O_{n+1}=O_n
\]

and

\[
S_{n+1}\neq S_n
\]

because the TAS_DNA datum extends authenticated lineage even though it does not enter the admitted projection.
