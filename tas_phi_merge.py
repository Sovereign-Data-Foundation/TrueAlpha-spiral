"""Pure dual-lattice merge; this module does not authenticate or authorize effects.

Inputs are typed records, not a wire format. A discharge requires an independently
configured verifier; the verifier is responsible for authenticating the proof,
its binding to the obligation, and any relevant policy, freshness and replay
checks. The boolean in a proof is only a necessary condition, never a verifier.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from tas_conformance_harness import SettlementSlice, allocation_digest


@dataclass(frozen=True)
class ExclusiveLock:
    key: str
    value: str


@dataclass(frozen=True)
class Obligation:
    obligationId: str
    kind: str  # "sticky" or "dischargeable"
    proofType: Optional[str] = None
    attestationDigest: Optional[str] = None
    exclusiveLock: Optional[ExclusiveLock] = None


@dataclass(frozen=True)
class DischargeProof:
    obligationId: str
    proofType: str
    attestationDigest: str
    signatureValid: bool


@dataclass(frozen=True)
class ParentArtifact:
    artifactId: str
    createdAtMs: int
    authorityU: int
    obligations: Sequence[Obligation]
    rawBps: int


@dataclass(frozen=True)
class MergeResult:
    authorityU: int
    obligations: tuple[Obligation, ...]
    allocations: tuple[SettlementSlice, ...]
    allocation_digest: str


ProofVerifier = Callable[[Obligation, DischargeProof], bool]


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain Unicode scalar values") from exc


def _natural(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _obligation(value: Obligation) -> None:
    if not isinstance(value, Obligation):
        raise TypeError("obligations must contain Obligation records")
    _text(value.obligationId, "obligationId")
    if value.kind not in ("sticky", "dischargeable"):
        raise ValueError("unknown obligation kind")
    if value.kind == "dischargeable":
        _text(value.proofType, "proofType")
        _text(value.attestationDigest, "attestationDigest")
    elif value.proofType is not None or value.attestationDigest is not None:
        raise ValueError("sticky obligations cannot specify discharge requirements")
    if value.exclusiveLock is not None:
        if not isinstance(value.exclusiveLock, ExclusiveLock):
            raise TypeError("exclusiveLock must be an ExclusiveLock")
        _text(value.exclusiveLock.key, "lock key")
        _text(value.exclusiveLock.value, "lock value")


def merge(
    parents: Sequence[ParentArtifact],
    proofs: Sequence[DischargeProof] = (),
    *,
    verifier: Optional[ProofVerifier] = None,
) -> MergeResult:
    """Intersect authority, union obligations, discharge verified proofs, normalize.

    Parent IDs must be unique. Identical obligations with the same ID are
    deduplicated; inconsistent definitions and duplicate proofs are rejected.
    Proofs for absent or sticky obligations are rejected. The complete rounding
    remainder goes to the first parent ordered by (createdAtMs, artifactId),
    which is also the allocation vector order used for the existing digest.
    Rejection raises TypeError or ValueError; verifier exceptions fail closed.
    """
    if not isinstance(parents, (list, tuple)) or not parents:
        raise ValueError("parents must be a nonempty list or tuple")
    if not isinstance(proofs, (list, tuple)):
        raise TypeError("proofs must be a list or tuple")
    if verifier is not None and not callable(verifier):
        raise TypeError("verifier must be callable")

    ids = set()
    obligations = {}
    authority = None
    for parent in parents:
        if not isinstance(parent, ParentArtifact):
            raise TypeError("parents must contain ParentArtifact records")
        _text(parent.artifactId, "artifactId")
        if parent.artifactId in ids:
            raise ValueError("duplicate parent artifactId")
        ids.add(parent.artifactId)
        _natural(parent.createdAtMs, "createdAtMs")
        _natural(parent.authorityU, "authorityU")
        _natural(parent.rawBps, "rawBps")
        if not isinstance(parent.obligations, (list, tuple)):
            raise TypeError("obligations must be a list or tuple")
        authority = parent.authorityU if authority is None else authority & parent.authorityU
        for obligation in parent.obligations:
            _obligation(obligation)
            existing = obligations.get(obligation.obligationId)
            if existing is not None and existing != obligation:
                raise ValueError("conflicting definitions for obligationId")
            obligations[obligation.obligationId] = obligation
    if not authority:
        raise ValueError("INCOMPATIBLE_LINEAGE_MERGE: authority meet is zero")
    total = sum(parent.rawBps for parent in parents)
    if not total:
        raise ValueError("raw basis point sum is zero")

    proof_by_id = {}
    for proof in proofs:
        if not isinstance(proof, DischargeProof):
            raise TypeError("proofs must contain DischargeProof records")
        _text(proof.obligationId, "proof obligationId")
        _text(proof.proofType, "proofType")
        _text(proof.attestationDigest, "attestationDigest")
        if type(proof.signatureValid) is not bool:
            raise TypeError("signatureValid must be a boolean")
        if proof.obligationId in proof_by_id:
            raise ValueError("duplicate proof obligationId")
        proof_by_id[proof.obligationId] = proof

    for obligation_id in sorted(proof_by_id):
        proof = proof_by_id[obligation_id]
        obligation = obligations.get(obligation_id)
        if obligation is None or obligation.kind != "dischargeable":
            raise ValueError("proof does not identify a dischargeable obligation")
        if (proof.proofType != obligation.proofType
                or proof.attestationDigest != obligation.attestationDigest
                or not proof.signatureValid):
            raise ValueError("proof does not satisfy obligation requirements")
        if verifier is None:
            raise ValueError("independent proof verifier required")
        try:
            verified = verifier(obligation, proof)
        except Exception as exc:
            raise ValueError("proof verifier failed") from exc
        if verified is not True:
            raise ValueError("proof verification failed")
        del obligations[obligation_id]

    active = tuple(obligations[key] for key in sorted(obligations))
    locks = {}
    for obligation in active:
        lock = obligation.exclusiveLock
        if lock is not None:
            if lock.key in locks and locks[lock.key] != lock.value:
                raise ValueError("INCOMPATIBLE_LINEAGE_MERGE: conflicting active exclusive locks")
            locks[lock.key] = lock.value

    ordered = sorted(parents, key=lambda parent: (parent.createdAtMs, parent.artifactId))
    amounts = [parent.rawBps * 10000 // total for parent in ordered]
    amounts[0] += 10000 - sum(amounts)
    allocations = tuple(
        SettlementSlice(parent.artifactId, amount)
        for parent, amount in zip(ordered, amounts)
    )
    return MergeResult(authority, active, allocations, allocation_digest(allocations))
