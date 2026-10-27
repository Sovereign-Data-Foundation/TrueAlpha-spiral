import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

import witness
from context_snapshot import canonical_json


def _bundle(tmp_path: Path, *, value: int = 450, bad_signature: bool = False) -> Path:
    root = tmp_path / "audit-bundle"
    (root / "manifests").mkdir(parents=True)
    (root / "lineage").mkdir()
    proposal = {
        "op": "SET_VARIABLE",
        "target": "grid_curtailment_limit",
        "value": value,
        "nonce": 1042,
        "authority_token": "AUTH_MUNICIPAL_ADMIN_v1",
        "proposer_pubkey": "key_admin_node_alpha",
    }
    payload = canonical_json({key: proposal[key] for key in ("op", "target", "value", "nonce")})
    proposal["auth_signature"] = sha256(payload + proposal["proposer_pubkey"].encode()).hexdigest()
    if bad_signature:
        proposal["auth_signature"] = "0" * 64
    manifest = {
        "crypto_suite": {"algorithm": "MOCK-DETERMINISTIC"},
        "proposal": proposal,
        "lineage_context": {
            "current_lineage_head": "0" * 64,
            "expected_parent_root": "0" * 64,
            "allowed_authority_tokens": ["AUTH_MUNICIPAL_ADMIN_v1"],
            "committed_nonces": [1040, 1041],
            "target_locked": False,
        },
        "receipt": {},
    }
    (root / "lineage" / "constraints.json").write_bytes(canonical_json({"max_value_bound": 1000}))
    provisional = witness.AuditBundle(manifest, {"max_value_bound": 1000})
    admitted, verdict = witness.evaluate(provisional)
    manifest["receipt"] = witness.recompute_receipt(provisional, admitted, verdict)
    (root / "manifests" / "receipt.json").write_bytes(canonical_json(manifest))
    return root


@pytest.mark.parametrize(
    ("value", "expected", "marker"),
    [(450, 0, "COMMITTED"), (15000, 10, "NULL_COLLAPSE")],
)
def test_cli_verifies_admission_and_conserved_refusal(tmp_path, value, expected, marker):
    root = _bundle(tmp_path, value=value)
    result = subprocess.run(
        [sys.executable, "witness.py", "verify", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected
    assert marker in result.stdout


def test_claimed_admission_with_bad_signature_is_authority_failure(tmp_path):
    root = _bundle(tmp_path, bad_signature=True)
    manifest_path = root / "manifests" / "receipt.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["receipt"]["status"] = "ADMITTED"
    manifest_path.write_bytes(canonical_json(manifest))
    assert witness.main(["verify", str(root)]) == witness.EXIT_AUTHORITY_FAILURE


def test_receipt_tampering_is_detected(tmp_path):
    root = _bundle(tmp_path)
    manifest_path = root / "manifests" / "receipt.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["receipt"]["delta_operational"] = 0
    manifest_path.write_bytes(canonical_json(manifest))
    assert witness.main(["verify", str(root)]) == witness.EXIT_RECEIPT_MISMATCH


def test_duplicate_manifest_keys_are_rejected(tmp_path):
    root = _bundle(tmp_path)
    manifest_path = root / "manifests" / "receipt.json"
    manifest_path.write_text('{"proposal":{},"proposal":{}}')
    assert witness.main(["verify", str(root)]) == witness.EXIT_MALFORMED_BUNDLE
