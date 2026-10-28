"""Unified state-lineage verifier.

The kernel implements the TAS transition invariant: operational state changes
*if and only if* authority, lineage, simulation, and post-state checks all pass.
A terminal receipt is emitted and the evidence timeline advances on every path.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, FrozenSet, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_DIGEST_SIZE = 32
_DOMAIN = b"TAS-HUMAN-AUTHORIZATION-V1\0"


class SovereignViolation(str, Enum):
    INVALID_SIGNATURE = "InvalidSignature"
    SCOPE_EXCEEDED = "ScopeExceeded"
    LINEAGE_DISCONTINUITY = "LineageDiscontinuity"
    CONTAINMENT_FAILURE = "ContainmentFailure"
    INVARIANT_BREACHED = "InvariantBreached"


@dataclass(frozen=True)
class OperationalState:
    data_root: bytes
    allowed_capabilities: FrozenSet[str]

    def __post_init__(self) -> None:
        if len(self.data_root) != _DIGEST_SIZE:
            raise ValueError("data_root must be 32 bytes")


@dataclass(frozen=True)
class LineageTimeline:
    parent_receipt_hash: bytes
    sequence_number: int

    def __post_init__(self) -> None:
        if len(self.parent_receipt_hash) != _DIGEST_SIZE or self.sequence_number < 0:
            raise ValueError("lineage requires a 32-byte parent hash and non-negative sequence")


@dataclass(frozen=True)
class HumanAuthorization:
    identity_key: bytes
    permitted_scopes: FrozenSet[str]
    signature: bytes
    revocation_nonce: int

    def __post_init__(self) -> None:
        if len(self.identity_key) != _DIGEST_SIZE or len(self.signature) != 64 or self.revocation_nonce < 0:
            raise ValueError("authorization key/signature/nonce is malformed")


@dataclass(frozen=True)
class ExecutionCandidate:
    targeted_action: str
    payload_hash: bytes
    raw_parameters: bytes
    expected_parent_receipt_hash: bytes

    def __post_init__(self) -> None:
        if not self.targeted_action or len(self.payload_hash) != _DIGEST_SIZE or len(self.expected_parent_receipt_hash) != _DIGEST_SIZE:
            raise ValueError("candidate action and hashes are required")
        if hashlib.sha256(self.raw_parameters).digest() != self.payload_hash:
            raise ValueError("payload_hash does not bind raw_parameters")


@dataclass(frozen=True)
class TerminalReceipt:
    parent_receipt_hash: bytes
    parent_state_hash: bytes
    sequence_number: int
    admission_gate_passed: bool
    resulting_state_hash: bytes | None
    violation_recorded: str | None
    computational_cost: int


SimulationEngine = Callable[[OperationalState, ExecutionCandidate], OperationalState]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> bytes:
    return hashlib.sha256(_canonical(value)).digest()


class UniversalVerifierKernel:
    """Pure transition kernel with unconditional, cryptographically chained evidence."""

    @staticmethod
    def authorization_payload(auth: HumanAuthorization, candidate: ExecutionCandidate) -> bytes:
        """Return the domain-separated bytes a human authority must sign."""
        return _DOMAIN + _canonical({
            "action": candidate.targeted_action,
            "identity_key": auth.identity_key.hex(),
            "payload_hash": candidate.payload_hash.hex(),
            "permitted_scopes": sorted(auth.permitted_scopes),
            "revocation_nonce": auth.revocation_nonce,
        })

    @staticmethod
    def process_transition(
        current_state: OperationalState,
        current_lineage: LineageTimeline,
        auth: HumanAuthorization,
        candidate: ExecutionCandidate,
        revocation_registry: Iterable[bytes],
        simulation_engine: SimulationEngine,
    ) -> tuple[OperationalState, LineageTimeline, TerminalReceipt]:
        """Audit, simulate, and atomically choose a commit or refusal trajectory.

        The supplied simulation is never called until static checks pass. Its
        output is accepted only when it cannot expand the current capability
        set; otherwise the original state is returned unchanged.
        """
        violation = UniversalVerifierKernel._audit(
            current_state, current_lineage, auth, candidate, frozenset(revocation_registry)
        )
        if violation:
            return UniversalVerifierKernel._refuse(current_state, current_lineage, violation)
        try:
            proposed_state = simulation_engine(current_state, candidate)
            if not isinstance(proposed_state, OperationalState):
                raise TypeError("simulation must return OperationalState")
        except Exception:
            return UniversalVerifierKernel._refuse(current_state, current_lineage, SovereignViolation.CONTAINMENT_FAILURE)
        if not proposed_state.allowed_capabilities.issubset(current_state.allowed_capabilities):
            return UniversalVerifierKernel._refuse(current_state, current_lineage, SovereignViolation.SCOPE_EXCEEDED)

        parent_state_hash = UniversalVerifierKernel.compute_state_digest(current_state)
        resulting_state_hash = UniversalVerifierKernel.compute_state_digest(proposed_state)
        receipt = TerminalReceipt(
            parent_receipt_hash=current_lineage.parent_receipt_hash,
            parent_state_hash=parent_state_hash,
            sequence_number=current_lineage.sequence_number,
            admission_gate_passed=True,
            resulting_state_hash=resulting_state_hash,
            violation_recorded=None,
            computational_cost=1,
        )
        return proposed_state, LineageTimeline(
            parent_receipt_hash=UniversalVerifierKernel.compute_receipt_digest(receipt),
            sequence_number=current_lineage.sequence_number + 1,
        ), receipt

    @staticmethod
    def _audit(state: OperationalState, lineage: LineageTimeline, auth: HumanAuthorization, candidate: ExecutionCandidate, revoked: FrozenSet[bytes]) -> SovereignViolation | None:
        if candidate.expected_parent_receipt_hash != lineage.parent_receipt_hash:
            return SovereignViolation.LINEAGE_DISCONTINUITY
        if auth.identity_key in revoked:
            return SovereignViolation.SCOPE_EXCEEDED
        # Authority (human scope) and capability (state permission) are separate gates.
        if candidate.targeted_action not in auth.permitted_scopes or candidate.targeted_action not in state.allowed_capabilities:
            return SovereignViolation.SCOPE_EXCEEDED
        try:
            Ed25519PublicKey.from_public_bytes(auth.identity_key).verify(
                auth.signature, UniversalVerifierKernel.authorization_payload(auth, candidate)
            )
        except (InvalidSignature, ValueError):
            return SovereignViolation.INVALID_SIGNATURE
        return None

    @staticmethod
    def _refuse(state: OperationalState, lineage: LineageTimeline, violation: SovereignViolation) -> tuple[OperationalState, LineageTimeline, TerminalReceipt]:
        receipt = TerminalReceipt(
            parent_receipt_hash=lineage.parent_receipt_hash,
            parent_state_hash=UniversalVerifierKernel.compute_state_digest(state),
            sequence_number=lineage.sequence_number,
            admission_gate_passed=False,
            resulting_state_hash=None,
            violation_recorded=violation.value,
            computational_cost=0,
        )
        return state, LineageTimeline(
            parent_receipt_hash=UniversalVerifierKernel.compute_receipt_digest(receipt),
            sequence_number=lineage.sequence_number + 1,
        ), receipt

    @staticmethod
    def compute_state_digest(state: OperationalState) -> bytes:
        return _digest({"allowed_capabilities": sorted(state.allowed_capabilities), "data_root": state.data_root.hex()})

    @staticmethod
    def compute_receipt_digest(receipt: TerminalReceipt) -> bytes:
        return _digest({
            "admission_gate_passed": receipt.admission_gate_passed,
            "computational_cost": receipt.computational_cost,
            "parent_receipt_hash": receipt.parent_receipt_hash.hex(),
            "parent_state_hash": receipt.parent_state_hash.hex(),
            "resulting_state_hash": receipt.resulting_state_hash.hex() if receipt.resulting_state_hash else None,
            "sequence_number": receipt.sequence_number,
            "violation_recorded": receipt.violation_recorded,
        })
