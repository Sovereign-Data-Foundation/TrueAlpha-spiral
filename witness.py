#!/usr/bin/env python3
"""Clean-room verifier for deterministic UL 3115 audit bundles.

The CLI intentionally performs no state mutation.  It recomputes the ordered
gate result and receipt from bundle inputs and reports the result through a
stable process exit code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_snapshot import CanonicalJSONError, canonical_json, parse_canonical_json

EXIT_VALID_ADMITTED = 0
EXIT_VALID_REFUSAL = 10
EXIT_MALFORMED_BUNDLE = 20
EXIT_DIGEST_LINEAGE_MISMATCH = 21
EXIT_AUTHORITY_FAILURE = 22
EXIT_RECEIPT_MISMATCH = 23
EXIT_UNSUPPORTED_CRYPTO = 24

SUPPORTED_CRYPTO_SUITES = frozenset({"ED25519-SHA256", "MOCK-DETERMINISTIC"})
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class WitnessFailure(Exception):
    """A stable verification failure intended for the command-line boundary."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _fail(exit_code: int, message: str) -> None:
    raise WitnessFailure(exit_code, message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return parse_canonical_json(path.read_bytes())
    except (OSError, CanonicalJSONError) as error:
        _fail(EXIT_MALFORMED_BUNDLE, f"cannot read {path}: {error}")


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(EXIT_MALFORMED_BUNDLE, f"{field} must be a JSON object")
    return value


@dataclass(frozen=True)
class AuditBundle:
    manifest: Mapping[str, Any]
    constraints: Mapping[str, Any]

    @classmethod
    def load(cls, root: Path) -> "AuditBundle":
        if not root.is_dir():
            _fail(EXIT_MALFORMED_BUNDLE, f"bundle is not a directory: {root}")
        manifests = root / "manifests"
        lineage = root / "lineage"
        if not manifests.is_dir() or not lineage.is_dir():
            _fail(EXIT_MALFORMED_BUNDLE, "required manifests/ or lineage/ directory missing")

        try:
            manifest_files = sorted(
                path for path in manifests.iterdir() if path.is_file() and path.suffix == ".json"
            )
        except OSError as error:
            _fail(EXIT_MALFORMED_BUNDLE, f"cannot enumerate manifests: {error}")
        if len(manifest_files) != 1:
            _fail(EXIT_MALFORMED_BUNDLE, "manifests/ must contain exactly one JSON file")

        manifest = _require_mapping(_read_json(manifest_files[0]), "manifest")
        required = {"proposal", "lineage_context", "receipt", "crypto_suite"}
        missing = sorted(required - manifest.keys())
        if missing:
            _fail(EXIT_MALFORMED_BUNDLE, f"manifest missing fields: {', '.join(missing)}")
        for field in required:
            _require_mapping(manifest[field], field)

        suite = manifest["crypto_suite"].get("algorithm")
        if suite not in SUPPORTED_CRYPTO_SUITES:
            _fail(EXIT_UNSUPPORTED_CRYPTO, f"unsupported cryptographic suite: {suite!r}")

        constraints_path = lineage / "constraints.json"
        constraints = (
            _require_mapping(_read_json(constraints_path), "constraints")
            if constraints_path.is_file()
            else {}
        )
        return cls(manifest=manifest, constraints=constraints)


class Gate:
    SIGNATURE = "01_SIGNATURE"
    AUTHORITY = "02_AUTHORITY"
    LINEAGE = "03_LINEAGE"
    CONTEXT = "04_CONTEXT"
    INVARIANTS = "05_INVARIANTS"
    REPLAY = "06_REPLAY"


def _proposal_payload(proposal: Mapping[str, Any]) -> bytes:
    required = ("op", "target", "value", "nonce")
    if any(field not in proposal for field in required):
        _fail(EXIT_MALFORMED_BUNDLE, "proposal lacks an op, target, value, or nonce")
    return canonical_json({field: proposal[field] for field in required})


def _verify_signature(algorithm: str, public_key: Any, signature: Any, payload: bytes) -> bool:
    if not isinstance(public_key, str) or not isinstance(signature, str):
        return False
    if algorithm == "MOCK-DETERMINISTIC":
        return signature == _sha256(payload + public_key.encode("utf-8"))

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        _fail(EXIT_UNSUPPORTED_CRYPTO, "ED25519-SHA256 requires the cryptography package")
    try:
        key_bytes = bytes.fromhex(public_key)
        signature_bytes = bytes.fromhex(signature)
        if len(key_bytes) != 32 or len(signature_bytes) != 64:
            return False
        Ed25519PublicKey.from_public_bytes(key_bytes).verify(signature_bytes, payload)
        return True
    except (ValueError, InvalidSignature):
        return False


def evaluate(bundle: AuditBundle) -> tuple[bool, str]:
    proposal = bundle.manifest["proposal"]
    lineage = bundle.manifest["lineage_context"]
    algorithm = bundle.manifest["crypto_suite"]["algorithm"]
    payload = _proposal_payload(proposal)

    if not _verify_signature(
        algorithm, proposal.get("proposer_pubkey"), proposal.get("auth_signature"), payload
    ):
        return False, Gate.SIGNATURE

    allowed = lineage.get("allowed_authority_tokens")
    if not isinstance(allowed, list) or proposal.get("authority_token") not in allowed:
        return False, Gate.AUTHORITY

    current = lineage.get("current_lineage_head")
    expected = lineage.get("expected_parent_root")
    if not isinstance(current, str) or not _HEX_64.fullmatch(current) or current != expected:
        return False, Gate.LINEAGE

    protected = bundle.constraints.get("protected_registers", [])
    if not isinstance(protected, list):
        _fail(EXIT_MALFORMED_BUNDLE, "protected_registers must be an array")
    if proposal["target"] in protected and lineage.get("target_locked") is True:
        return False, Gate.CONTEXT

    maximum = bundle.constraints.get("max_value_bound")
    value = proposal["value"]
    if maximum is not None:
        if isinstance(maximum, bool) or not isinstance(maximum, int):
            _fail(EXIT_MALFORMED_BUNDLE, "max_value_bound must be an integer")
        if isinstance(value, bool) or not isinstance(value, int) or value > maximum:
            return False, Gate.INVARIANTS

    nonces = lineage.get("committed_nonces")
    nonce = proposal["nonce"]
    if not isinstance(nonces, list):
        _fail(EXIT_MALFORMED_BUNDLE, "committed_nonces must be an array")
    if isinstance(nonce, bool) or not isinstance(nonce, int) or nonce in nonces:
        return False, Gate.REPLAY
    return True, "ALL_GATES_PASSED"


def recompute_receipt(bundle: AuditBundle, admitted: bool, verdict: str) -> dict[str, Any]:
    proposal = bundle.manifest["proposal"]
    lineage = bundle.manifest["lineage_context"]
    body: dict[str, Any] = {
        "status": "ADMITTED" if admitted else "REFUSED",
        "first_failed_gate": None if admitted else verdict,
        "gate_reason": verdict,
        "lineage_head_in": lineage.get("current_lineage_head"),
        "proposal_digest": _sha256(_proposal_payload(proposal)),
        "delta_operational": 1 if admitted else 0,
        "delta_lineage": 1,
    }
    body["receipt_sha256"] = _sha256(canonical_json(body))
    return body


def verify_bundle(root: Path) -> tuple[int, str]:
    bundle = AuditBundle.load(root)
    current = bundle.manifest["lineage_context"].get("current_lineage_head")
    if not isinstance(current, str) or not _HEX_64.fullmatch(current):
        _fail(EXIT_DIGEST_LINEAGE_MISMATCH, "current_lineage_head is not a SHA-256 digest")

    admitted, verdict = evaluate(bundle)
    receipt = bundle.manifest["receipt"]
    if not admitted and verdict in (Gate.SIGNATURE, Gate.AUTHORITY):
        if receipt.get("status") == "ADMITTED":
            _fail(EXIT_AUTHORITY_FAILURE, f"admission claim failed {verdict}")

    expected = recompute_receipt(bundle, admitted, verdict)
    if canonical_json(receipt) != canonical_json(expected):
        _fail(
            EXIT_RECEIPT_MISMATCH,
            "receipt recomputation divergence "
            f"(expected {_sha256(canonical_json(expected))}, supplied {_sha256(canonical_json(receipt))})",
        )
    if admitted:
        return EXIT_VALID_ADMITTED, f"[WITNESS: COMMITTED] {receipt['receipt_sha256']}"
    return EXIT_VALID_REFUSAL, f"[WITNESS: NULL_COLLAPSE] {verdict} {receipt['receipt_sha256']}"


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2 or arguments[0] != "verify":
        sys.stderr.write("Usage: witness.py verify <audit-bundle-dir>\n")
        return EXIT_MALFORMED_BUNDLE
    try:
        code, message = verify_bundle(Path(os.fsdecode(arguments[1])))
    except WitnessFailure as error:
        sys.stderr.write(f"[WITNESS_FAIL_{error.exit_code}] {error}\n")
        return error.exit_code
    print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
