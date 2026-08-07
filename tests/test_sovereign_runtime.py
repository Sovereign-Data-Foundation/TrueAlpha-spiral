import pytest
import sqlite3
from pathlib import Path
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.runtime import (
    AdmissibilityObject,
    TASGene,
    WakeChain,
    SovereignRuntime,
)
from core.runtime.sovereign_runtime import SovereignStructuralViolation, sha256_uri


def create_admissibility_object(
    credential_id="steward-1",
    scope="increment",
    authority_snapshot=None,
    context_snapshot_hash="sha256:context-01",
    candidate_hash="sha256:candidate-01",
    parent_receipt="sha256:genesis",
    revocation_result=False,
    invariant_results=None,
    closed_admitted_action_set=None,
    decision="ADMITTED",
    verifier_priv=None,
):
    if authority_snapshot is None:
        authority_snapshot = {"credential_id": credential_id, "authority_epoch": 7, "authority_checkpoint_hash": "sha256:checkpoint", "revoked": False}
    if invariant_results is None:
        invariant_results = {"schema": True}
    if closed_admitted_action_set is None:
        closed_admitted_action_set = {"increment"}
    if verifier_priv is None:
        verifier_priv = ed25519.Ed25519PrivateKey.generate()

    # Create dummy object to compute its receipt hash
    temp_obj = AdmissibilityObject(
        credential_id=credential_id,
        scope=scope,
        authority_snapshot=authority_snapshot,
        context_snapshot_hash=context_snapshot_hash,
        candidate_hash=candidate_hash,
        parent_receipt=parent_receipt,
        revocation_result=revocation_result,
        invariant_results=invariant_results,
        closed_admitted_action_set=closed_admitted_action_set,
        decision=decision,
        receipt_hash="",
        signature=b"",
    )

    receipt_hash = temp_obj.compute_receipt_hash()
    signature = verifier_priv.sign(receipt_hash.encode())

    return AdmissibilityObject(
        credential_id=credential_id,
        scope=scope,
        authority_snapshot=authority_snapshot,
        context_snapshot_hash=context_snapshot_hash,
        candidate_hash=candidate_hash,
        parent_receipt=parent_receipt,
        revocation_result=revocation_result,
        invariant_results=invariant_results,
        closed_admitted_action_set=closed_admitted_action_set,
        decision=decision,
        receipt_hash=receipt_hash,
        signature=signature,
    )


def test_vertical_slice_path_1_admitted():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()
    runtime_pub = runtime_priv.public_key()

    authority_snapshot = {
        "credential_id": "steward-1",
        "authority_epoch": 7,
        "authority_checkpoint_hash": "sha256:checkpoint",
        "revoked": False,
    }

    obj = create_admissibility_object(
        scope="increment",
        authority_snapshot=authority_snapshot,
        verifier_priv=verifier_priv,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(obj)

    assert result["decision"] == "COMMITTED"
    assert result["operation"] == "increment"
    assert result["state"]["value"] == 11
    assert result["receipt_hash"] == obj.receipt_hash
    assert "wake_link" in result

    # Verify the terminal signature
    terminal_message = (
        b"SDF-TERMINAL-COMMITTED-V1\0"
        + json_canonical({"decision": "COMMITTED", "operation": "increment", "state_hash": result["state_hash"], "state": result["state"], "wake_link": result["wake_link"], "receipt_hash": obj.receipt_hash})
    )
    sig_bytes = bytes.fromhex(result["attestation"]["signature"])
    runtime_pub.verify(sig_bytes, terminal_message)

    # Verify WakeChain state history updated
    assert len(runtime.wake_chain.state_history) == 1
    assert len(runtime.wake_chain.evidence_history) == 1
    assert runtime.wake_chain.state_head_hash == obj.receipt_hash


def test_vertical_slice_path_2_refused_due_to_signature():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    obj = create_admissibility_object(verifier_priv=verifier_priv)

    # Tamper with signature
    tampered_obj = AdmissibilityObject(
        credential_id=obj.credential_id,
        scope=obj.scope,
        authority_snapshot=obj.authority_snapshot,
        context_snapshot_hash=obj.context_snapshot_hash,
        candidate_hash=obj.candidate_hash,
        parent_receipt=obj.parent_receipt,
        revocation_result=obj.revocation_result,
        invariant_results=obj.invariant_results,
        closed_admitted_action_set=obj.closed_admitted_action_set,
        decision=obj.decision,
        receipt_hash=obj.receipt_hash,
        signature=b"0" * 64,  # Bad signature
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(tampered_obj)

    assert result["decision"] == "REFUSED"
    assert result["state"]["value"] == 10
    assert "signature_validity" in result["failures"]


def test_binding_integrity_substitution_gap_blocked():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    obj = create_admissibility_object(verifier_priv=verifier_priv)

    # Keep signature and receipt_hash of the valid object, but change candidate_hash!
    # This simulates an attacker substituting the candidate_hash while keeping a valid signature.
    tampered_obj = AdmissibilityObject(
        credential_id=obj.credential_id,
        scope=obj.scope,
        authority_snapshot=obj.authority_snapshot,
        context_snapshot_hash=obj.context_snapshot_hash,
        candidate_hash="sha256:TAMPERED-CANDIDATE",
        parent_receipt=obj.parent_receipt,
        revocation_result=obj.revocation_result,
        invariant_results=obj.invariant_results,
        closed_admitted_action_set=obj.closed_admitted_action_set,
        decision=obj.decision,
        receipt_hash=obj.receipt_hash,  # Trusted blindly in old code
        signature=obj.signature,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(tampered_obj)

    assert result["decision"] == "REFUSED"
    assert "binding_integrity" in result["failures"]


def test_closed_admitted_action_set_exact_membership_enforced():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    # Scope is "increment", but closed_admitted_action_set only contains "different-action"
    obj = create_admissibility_object(
        scope="increment",
        closed_admitted_action_set={"different-action"},
        verifier_priv=verifier_priv,
    )

    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 10},
    )

    result = runtime.execute_action(obj)

    assert result["decision"] == "REFUSED"
    assert "scope_authorization" in result["failures"]


def test_crash_durability_wal_sqlite(tmp_path):
    db_file = tmp_path / "ledger.db"

    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    # 1. Initialize runtime with db_path and execute an admitted action
    runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 50},
        db_path=db_file,
    )

    obj_1 = create_admissibility_object(
        scope="increment",
        parent_receipt="sha256:genesis",
        verifier_priv=verifier_priv,
    )

    result_1 = runtime.execute_action(obj_1)
    assert result_1["decision"] == "COMMITTED"
    assert result_1["state"]["value"] == 51

    # Record the heads
    link_1 = result_1["wake_link"]
    head_1 = runtime.wake_chain.state_head_hash

    # 2. Simulate complete crash and restart by re-instantiating SovereignRuntime with same db_path
    restored_runtime = SovereignRuntime(
        verifier_public_key=verifier_pub_bytes,
        runtime_private_key=runtime_priv_bytes,
        genesis_state={"value": 999},  # ignored since state is loaded from SQLite
        db_path=db_file,
    )

    # Verify state, histories, and heads are fully restored
    assert restored_runtime.state["value"] == 51
    assert restored_runtime.wake_chain.state_head_hash == head_1
    assert restored_runtime.wake_chain.last_wake_link == link_1
    assert len(restored_runtime.wake_chain.state_history) == 1
    assert len(restored_runtime.wake_chain.evidence_history) == 1

    gene = restored_runtime.wake_chain.state_history[0]
    assert gene.operation == "increment"
    assert gene.receipt["receipt_hash"] == obj_1.receipt_hash

    # 3. Execute a second action sequentially and verify continuity
    obj_2 = create_admissibility_object(
        scope="increment",
        parent_receipt=head_1,  # correct sequential parent
        verifier_priv=verifier_priv,
    )

    result_2 = restored_runtime.execute_action(obj_2)
    assert result_2["decision"] == "COMMITTED"
    assert result_2["state"]["value"] == 52
    assert restored_runtime.wake_chain.state_head_hash == obj_2.receipt_hash


def test_wake_chain_state_discontinuity_raises_structural_violation():
    verifier_priv = ed25519.Ed25519PrivateKey.generate()
    verifier_pub_bytes = verifier_priv.public_key().public_bytes_raw()

    runtime_priv = ed25519.Ed25519PrivateKey.generate()
    runtime_priv_bytes = runtime_priv.private_bytes_raw()

    obj = create_admissibility_object(
        parent_receipt="sha256:unexpected-parent",
        verifier_priv=verifier_priv,
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
    with pytest.raises(ValueError, match="origin is required"):
        gene = TASGene("", "context", "auth", "op", "parent", {}, "ADMITTED", {"receipt_hash": "hash"})
        gene.constitutional_completeness_check()

    with pytest.raises(ValueError, match="decision must be ADMITTED or REFUSED"):
        gene = TASGene("origin", "context", "auth", "op", "parent", {}, "INVALID", {"receipt_hash": "hash"})
        gene.constitutional_completeness_check()

    gene = TASGene("origin", "context", "auth", "op", "parent", {}, "ADMITTED", {"receipt_hash": "hash"})
    assert gene.constitutional_completeness_check() is True


def json_canonical(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
