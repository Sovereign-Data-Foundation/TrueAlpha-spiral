from copy import deepcopy

from sdf_admissibility_daemon import canonical_json, evaluate_transition, sha256_uri


PARENT_HASH = "sha256:genesis"


def valid_transition():
    return {
        "receipt_id": "sdf-exec-test000001",
        "timestamp_utc": "2026-07-08T00:00:00Z",
        "origin": {
            "origin_id": "human_api_key_001",
            "origin_type": "human",
            "authority_source": "explicit_user_intent",
            "jurisdiction": "US-TX",
            "timestamp_utc": "2026-07-08T00:00:00Z",
            "issued_at": "2026-07-08T00:00:00Z",
            "nonce": "unique-replay-resistant-value",
        },
        "authority": {
            "authority_scope": [
                "read_context",
                "generate_receipt",
                "refuse_invalid_transition",
            ],
            "denied_capabilities": [
                "modify_private_state_without_consent",
                "execute_external_tool_without_receipt",
                "suppress_refusal_reason",
            ],
            "consent_required": True,
            "revocable": True,
            "valid_until": "2026-07-17T00:00:00Z",
            "scope_policy": ["read_context", "generate_receipt", "refuse_invalid_transition"],
        },
        "lineage": {
            "parent_hash": PARENT_HASH,
            "lineage_hash": "sha256:current-transition-lineage",
            "genesis_hash": "sha256:root-anchor",
            "app_hash": "sha256:canonical-app-state",
            "receipt_chain_id": "sdf-logos-chain-001",
        },
        "expected_parent_hash": PARENT_HASH,
        "consent": {"granted": True},
        "privacy": {
            "substance_retention": "sovereign",
            "proof_surface": "public",
            "private_payload_storage": False,
            "hash_private_payload": True,
            "reveal_private_content": False,
            "audit_without_extraction": True,
        },
        "action_requested": ["read_context", "generate_receipt"],
        "tools_invoked": [],
    }


def test_accepts_valid_origin_authority_lineage():
    receipt = evaluate_transition(valid_transition())
    assert receipt["receipt_type"] == "execution"
    assert receipt["admissibility_result"] == "accepted"
    assert receipt["action_authorized"] is True
    assert receipt["failed_invariants"] == []


def test_refuses_missing_authority():
    transition = valid_transition()
    transition["receipt_id"] = "sdf-refusal-test000001"
    transition["authority"]["authority_scope"] = ["read_context"]
    receipt = evaluate_transition(transition)
    assert receipt["receipt_type"] == "refusal"
    assert "authority_match" in receipt["failed_invariants"]


def test_refuses_broken_parent_hash():
    transition = valid_transition()
    transition["receipt_id"] = "sdf-refusal-test000002"
    transition["lineage"]["parent_hash"] = "sha256:tampered"
    receipt = evaluate_transition(transition)
    assert receipt["admissibility_result"] == "refused"
    assert "lineage_continuity" in receipt["failed_invariants"]


def test_refuses_missing_consent():
    transition = valid_transition()
    transition["receipt_id"] = "sdf-refusal-test000003"
    transition["consent"] = {"granted": False}
    receipt = evaluate_transition(transition)
    assert receipt["action_authorized"] is False
    assert "consent_validity" in receipt["failed_invariants"]


def test_emits_refusal_receipt():
    transition = valid_transition()
    transition["receipt_id"] = "sdf-refusal-test000004"
    transition["origin"]["nonce"] = ""
    receipt = evaluate_transition(transition)
    assert receipt["receipt_type"] == "refusal"
    assert receipt["refusal_reason"] == "DENIED_AUTHORIZATION"
    assert receipt["receipt_hash"].startswith("sha256:")


def test_never_changes_state_on_refusal():
    transition = valid_transition()
    transition["receipt_id"] = "sdf-refusal-test000005"
    transition["privacy"]["private_payload_storage"] = True
    before = deepcopy(transition)
    receipt = evaluate_transition(transition)
    assert transition == before
    assert receipt["state_changed"] is False


def test_receipt_is_canonical_and_hashable():
    receipt = evaluate_transition(valid_transition())
    canonical = canonical_json({k: v for k, v in receipt.items() if k != "receipt_hash"})
    assert canonical == canonical_json({k: v for k, v in receipt.items() if k != "receipt_hash"})
    assert receipt["receipt_hash"] == sha256_uri({k: v for k, v in receipt.items() if k != "receipt_hash"})


def test_nonce_is_consumed_atomically_and_conflicts_fail_closed():
    from sdf_admissibility_daemon import AdmissibilityDaemon

    daemon = AdmissibilityDaemon()
    transition = valid_transition()
    first = daemon.evaluate(transition, current_time="2026-07-08T01:00:00Z")
    assert first["admissibility_result"] == "accepted"
    assert daemon.evaluate(transition, current_time="2026-07-08T01:00:00Z") == first

    conflicting = valid_transition()
    conflicting["action_requested"] = ["read_context"]
    cutoff = daemon.evaluate(conflicting, current_time="2026-07-08T01:00:00Z")
    assert cutoff["admissibility_result"] == "CUTOFF"
    assert cutoff["cutoff_reason"] == "LINEAGE_OR_REPLAY_INVALID"


def test_scope_policy_and_normalized_time_are_enforced():
    from sdf_admissibility_daemon import AdmissibilityDaemon

    daemon = AdmissibilityDaemon()
    out_of_scope = valid_transition()
    out_of_scope["authority"]["scope_policy"] = ["read_context"]
    receipt = daemon.evaluate(out_of_scope, current_time="2026-07-08T01:00:00Z")
    assert "scope_authorization" in receipt["failed_invariants"]

    expired = valid_transition()
    expired["authority"]["valid_until"] = "2026-07-08T00:30:00-01:00"
    receipt = daemon.evaluate(expired, current_time="2026-07-08T01:31:00Z")
    assert "authority_match" in receipt["failed_invariants"]


def test_raw_ingress_rejects_duplicate_keys_and_all_floats_without_receipt():
    from sdf_admissibility_daemon import AdmissibilityDaemon

    daemon = AdmissibilityDaemon()
    assert daemon.evaluate_raw(b'{"origin":{},"origin":{}}') is None
    assert daemon.evaluate_raw(b'{"value":3.0}') is None


def test_child_requires_an_authenticated_parent_receipt():
    from sdf_admissibility_daemon import AdmissibilityDaemon

    daemon = AdmissibilityDaemon()
    parent = daemon.evaluate(valid_transition(), current_time="2026-07-08T01:00:00Z")
    child = valid_transition()
    child["receipt_id"] = "sdf-exec-test000002"
    child["origin"]["nonce"] = "second-replay-resistant-value"
    child["lineage"]["parent_hash"] = parent["receipt_hash"]
    child["expected_parent_hash"] = parent["receipt_hash"]
    assert daemon.evaluate(child, current_time="2026-07-08T01:00:00Z")["admissibility_result"] == "accepted"


def test_parent_verifier_can_require_an_external_trust_root():
    from sdf_admissibility_daemon import AdmissibilityDaemon

    daemon = AdmissibilityDaemon(parent_verifier=lambda _hash, _receipt: False)
    parent = daemon.evaluate(valid_transition(), current_time="2026-07-08T01:00:00Z")
    child = valid_transition()
    child["origin"]["nonce"] = "externally-untrusted-parent"
    child["lineage"]["parent_hash"] = parent["receipt_hash"]
    child["expected_parent_hash"] = parent["receipt_hash"]
    refusal = daemon.evaluate(child, current_time="2026-07-08T01:00:00Z")
    assert "lineage_continuity" in refusal["failed_invariants"]
