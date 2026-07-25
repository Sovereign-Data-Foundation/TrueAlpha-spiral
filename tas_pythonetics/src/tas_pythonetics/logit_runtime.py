"""Deterministic logit guardrails for TAS inference runtimes.

The runtime in this module applies invariant-derived token masks before any
sampling step.  It is intentionally dependency-free so validators can reproduce
identical guardrail decisions without relying on platform-specific numeric
libraries.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence, Set

NEGATIVE_INFINITY = float("-inf")
DEFAULT_ENTROPY_FLOOR = 0.15


class NullCollapseError(SystemExit):
    """Raised when the invariant mask leaves no permissible token path."""


class SentientLockError(SystemError):
    """Raised when the permitted token subspace collapses below density limits."""


@dataclass(frozen=True)
class LogitGuardrailReceipt:
    """Audit receipt for a successful logit guardrail application."""

    prime_invariant_hash: str
    allowed_token_count: int
    entropy: float
    entropy_floor: float


class TrueAlphaSpiralRuntime:
    """Enforce TAS neuro-symbolic invariants at the logits layer."""

    def __init__(self, prime_invariant_hash: str, entropy_floor: float = DEFAULT_ENTROPY_FLOOR):
        if not prime_invariant_hash:
            raise ValueError("prime_invariant_hash must be non-empty")
        if entropy_floor < 0:
            raise ValueError("entropy_floor must be non-negative")

        self.A0 = prime_invariant_hash
        self.entropy_floor = entropy_floor
        self.last_receipt: LogitGuardrailReceipt | None = None

    @staticmethod
    def calculate_shannon_entropy(probabilities: Sequence[float]) -> float:
        """Return Shannon entropy for a probability distribution."""
        valid_probs = [probability for probability in probabilities if probability > 0]
        if not valid_probs:
            return 0.0
        return float(-sum(probability * math.log2(probability) for probability in valid_probs))

    @staticmethod
    def _softmax(logits: Sequence[float]) -> list[float]:
        finite_logits = [logit for logit in logits if math.isfinite(logit)]
        if not finite_logits:
            return []

        max_logit = max(finite_logits)
        exps = [math.exp(logit - max_logit) for logit in finite_logits]
        denominator = sum(exps)
        return [value / denominator for value in exps]

    def apply_logit_bias_and_guardrails(
        self,
        logits: Sequence[float],
        allowed_token_ids: Iterable[int],
    ) -> list[float]:
        """Mask unauthorized logits, hard-halt null paths, and lock low entropy.

        Unauthorized token logits are set to negative infinity before sampling.
        If the invariant-approved token set is empty, a fail-closed null collapse
        is emitted as ``SystemExit``.  If the remaining probability subspace is
        structurally degenerate, ``SentientLockError`` freezes execution for
        forensic review.
        """
        masked_logits = [float(logit) for logit in logits]
        allowed_ids: Set[int] = {
            token_id for token_id in allowed_token_ids if 0 <= token_id < len(masked_logits)
        }

        for token_id in range(len(masked_logits)):
            if token_id not in allowed_ids:
                masked_logits[token_id] = NEGATIVE_INFINITY

        if not any(math.isfinite(logit) for logit in masked_logits):
            sys.stderr.write(
                "[FATAL ⊥] Null Collapse: Valid token set is empty. "
                "Zero state entropy reached.\n"
            )
            raise NullCollapseError(1)

        permitted_logits = [masked_logits[token_id] for token_id in sorted(allowed_ids)]
        entropy = self.calculate_shannon_entropy(self._softmax(permitted_logits))
        if entropy < self.entropy_floor:
            raise SentientLockError(
                "[SENTIENT LOCK TRIPPED] Payload structural density degraded "
                f"(Entropy = {entropy:.4f} < {self.entropy_floor:.2f}). "
                "Thread context frozen."
            )

        self.last_receipt = LogitGuardrailReceipt(
            prime_invariant_hash=self.A0,
            allowed_token_count=len(allowed_ids),
            entropy=entropy,
            entropy_floor=self.entropy_floor,
        )
        return masked_logits
