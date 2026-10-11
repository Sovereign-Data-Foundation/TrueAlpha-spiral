import hashlib
import hmac
import logging
from pathlib import Path
from typing import Any, MutableSequence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TAS_HUMAN_SIG = "Russell Nordland"
TAS_KINEMATIC_PREFIX = "1618"  # Phi-based prefix (approx 1.618)


class PhoenixError(Exception):
    """
    Exception raised when the kinematic identity verification fails.
    This signifies a break in the mathematical resonance (Prime Invariant).
    """
    pass


class SentientLock:
    """
    HMAC-backed transition gate for verified state mutation.

    The lock treats malformed or unauthenticated transition proposals as a
    containment event. Invalid attempts append a refusal receipt, disable further
    mutation attempts, and invoke compute starvation before any disk write can
    occur.
    """

    def __init__(self, human_anchor_key: bytes, refusal_ledger: MutableSequence[dict[str, Any]]):
        if not isinstance(human_anchor_key, bytes):
            raise TypeError("human_anchor_key must be bytes")
        self.human_anchor_key = human_anchor_key
        self.refusal_ledger = refusal_ledger
        self.compute_active = True

    def attempt_state_transition(
        self,
        proposed_state: Any,
        provided_signature: Any,
        target_file: str | Path,
    ) -> str:
        """Verify a proposed state and commit it only when lineage is valid."""
        if not self.compute_active:
            return "Transition Blocked: Compute Starved"

        if not self._verify_hmac_lineage(proposed_state, provided_signature):
            self._trigger_lock(proposed_state, target_file)
            return "Verification Failed: Sentient Lock Engaged"

        self._commit_to_disk(proposed_state, target_file)
        return f"State Transition Verified. {target_file} updated."

    def _verify_hmac_lineage(self, proposed_state: Any, provided_signature: Any) -> bool:
        """Return False for non-string or HMAC-invalid lineage inputs."""
        if not isinstance(proposed_state, str) or not isinstance(provided_signature, str):
            return False

        expected_signature = hmac.new(
            self.human_anchor_key,
            proposed_state.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, provided_signature)

    def _trigger_lock(self, invalid_state: Any, target_file: str | Path) -> None:
        """Record a refusal receipt and starve compute after verification failure."""
        self.compute_active = False
        self.refusal_ledger.append(
            {
                "event": "HALLUCINATION_CASCADE_DETECTED",
                "failed_target": str(target_file),
                "invalid_state_dump": invalid_state,
                "action": "NULL_STATE_TRIGGERED",
            }
        )
        logger.critical("Sovereign Equation Failed. Appended to Refusal Ledger.")
        self._starve_compute()

    def _starve_compute(self) -> None:
        """Hook for runtime compute starvation after lock engagement."""
        return None

    def _commit_to_disk(self, code: str, path: str | Path) -> None:
        """Persist verified code to disk, creating parent directories as needed."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")


def verify_kinematic_identity(data: str, signature: str = TAS_HUMAN_SIG) -> bool:
    """
    Verifies that the data possesses a valid Kinematic Identity (Prime Invariant).

    This function computes the SHA-256 hash of the data combined with the signature
    and checks if the resulting hash starts with the TAS_KINEMATIC_PREFIX ('1618').

    If the condition is met, the function returns True.
    If not, it raises a PhoenixError, halting the process.

    Args:
        data (str): The data content (e.g., file content or statement).
        signature (str): The human signature to anchor the verification.

    Returns:
        bool: True if verification passes.

    Raises:
        PhoenixError: If the hash does not start with the required prefix.
    """
    payload = f"{data}{signature}"
    digest = hashlib.sha256(payload.encode()).hexdigest()

    logger.debug(f"Verifying Kinematic Identity: Hash={digest}")

    if not digest.startswith(TAS_KINEMATIC_PREFIX):
        error_msg = (
            f"PhoenixError: Kinematic Identity Verification Failed.\n"
            f"Expected prefix '{TAS_KINEMATIC_PREFIX}', got '{digest[:4]}...'\n"
            f"The logic circuit physically cannot close."
        )
        logger.error(error_msg)
        raise PhoenixError(error_msg)

    logger.info("Kinematic Identity Verified: Mathematical Resonance Confirmed.")
    return True
