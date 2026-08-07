import pytest
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.runtime import (
    AdmissibilityObject,
    TASGene,
    WakeChain,
    SovereignRuntime,
)
from core.runtime.sovereign_runtime import SovereignStructuralViolation, sha256_uri


def test_vertical_slice_path_1_admitted():
    # 1. Setup keys
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub = verifier_priv.public_key()
    verifier_pub_bytes = verifier_pub.public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()
    runtime_pub = runtime_priv.public_key()

    # 2. Build admissibility receipt_hash
    receipt_hash = "sha256:admissible-receipt-01"
    signature = verifier_priv.sign(receipt_hash.encode())

    # Create immutable verifier admissibility object
    obj = AdmissibilityObject(
        credential_id="steward-1",
        scope="increment",
        authority_snapshot={"public_key": verifier_pub_bytes, "revoked": False},
        context_snapshot_hash="sha256:context-01",
        candidate_hash="sha256:candidate-01",
        parent_receipt="sha256:genesis",
        revocation_result=False,
        invariant_results={"schema": True, "bounds": True},
        closed_admitted_action_set={"increment"},
        decision="ADMITTED",
        receipt_hash=receipt_hash,
        signature=signature,
    )

    # 3. Instantiate Runtime and execute action
    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(obj)

    # Assertions for ADMITTED path
    assert result["decision"] == "COMMITTED"
    assert result["operation"] == "increment"
    assert result["state"]["value"] == 11
    assert result["receipt_hash"] == receipt_hash
    assert "wake_link" in result

    # Verify the terminal signature
    terminal_message = (
        b"SDF-TERMINAL-COMMITTED-V1\0"
        + json_canonical({"decision": "COMMITTED", "operation": "increment", "state_hash": result["state_hash"], "state": result["state"], "wake_link": result["wake_link"], "receipt_hash": receipt_hash})
    )
    sig_bytes = bytes.fromhex(result["attestation"]["signature"])
    runtime_pub.verify(sig_bytes, terminal_message)

    # Verify WakeChain state history updated
    assert len(runtime.wake_chain.state_history) == 1
    assert len(runtime.wake_chain.evidence_history) == 1
    assert runtime.wake_chain.state_head_hash == receipt_hash


def test_vertical_slice_path_2_refused_due_to_signature():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    # Bad signature
    bad_signature = b"0" * 64

    obj = AdmissibilityObject(
        credential_id="steward-1",
        scope="increment",
        authority_snapshot={"public_key": verifier_pub_bytes, "revoked": False},
        context_snapshot_hash="sha256:context-01",
        candidate_hash="sha256:candidate-01",
        parent_receipt="sha256:genesis",
        revocation_result=False,
        invariant_results={"schema": True},
        closed_admitted_action_set=set(),
        decision="ADMITTED",
        receipt_hash="sha256:admissible-receipt-01",
        signature=bad_signature,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(obj)

    # Assertions for REFUSED path
    assert result["decision"] == "REFUSED"
    assert result["state"]["value"] == 10  # State must NOT change
    assert "signature_validity" in result["failures"]

    # Verify refusal is in evidence history but NOT state history
    assert len(runtime.wake_chain.state_history) == 0
    assert len(runtime.wake_chain.evidence_history) == 1
    assert runtime.wake_chain.state_head_hash == "sha256:genesis"


def test_vertical_slice_path_2_refused_due_to_revocation():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub = verifier_priv.public_key()
    verifier_pub_bytes = verifier_pub.public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    receipt_hash = "sha256:admissible-receipt-01"
    signature = verifier_priv.sign(receipt_hash.encode())

    # Revoked snapshot
    obj = AdmissibilityObject(
        credential_id="steward-1",
        scope="increment",
        authority_snapshot={"public_key": verifier_pub_bytes, "revoked": True},
        context_snapshot_hash="sha256:context-01",
        candidate_hash="sha256:candidate-01",
        parent_receipt="sha256:genesis",
        revocation_result=True,
        invariant_results={"schema": True},
        closed_admitted_action_set={"increment"},
        decision="ADMITTED",
        receipt_hash=receipt_hash,
        signature=signature,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(obj)

    assert result["decision"] == "REFUSED"
    assert result["state"]["value"] == 10
    assert "authority_match" in result["failures"]


def test_wake_chain_state_discontinuity_raises_structural_violation():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    # Expected parent is different from current state head (genesis)
    receipt_hash = "sha256:admissible-receipt-01"
    signature = verifier_priv.sign(receipt_hash.encode())

    obj = AdmissibilityObject(
        credential_id="steward-1",
        scope="increment",
        authority_snapshot={"public_key": verifier_pub_bytes, "revoked": False},
        context_snapshot_hash="sha256:context-01",
        candidate_hash="sha256:candidate-01",
        parent_receipt="sha256:unexpected-parent",
        revocation_result=False,
        invariant_results={"schema": True},
        closed_admitted_action_set={"increment"},
        decision="ADMITTED",
        receipt_hash=receipt_hash,
        signature=signature,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    with pytest.raises(SovereignStructuralViolation) as excinfo:
        runtime.execute_action(obj)

    assert "State linkage discontinuity" in str(excinfo.value)


def test_tas_gene_constitutional_completeness():
    # Missing or invalid fields should raise ValueError in constitutional completeness check
    with pytest.raises(ValueError, match="origin is required"):
        gene = TASGene("", "context", "auth", "op", "parent", {}, "ADMITTED", {"receipt_hash": "hash"})
        gene.constitutional_completeness_check()

    with pytest.raises(ValueError, match="decision must be ADMITTED or REFUSED"):
        gene = TASGene("origin", "context", "auth", "op", "parent", {}, "INVALID", {"receipt_hash": "hash"})
        gene.constitutional_completeness_check()

    # Valid gene passes
    gene = TASGene("origin", "context", "auth", "op", "parent", {}, "ADMITTED", {"receipt_hash": "hash"})
    assert gene.constitutional_completeness_check() is True


def json_canonical(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
