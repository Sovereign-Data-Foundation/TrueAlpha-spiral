from copy import deepcopy

from sdf_admissibility_daemon import canonical_json, evaluate_transition, sha256_uri


PARENT_HASH = "sha256:previous-valid-state"


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
            "expires_at": "2026-07-09T00:00:00Z",
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
