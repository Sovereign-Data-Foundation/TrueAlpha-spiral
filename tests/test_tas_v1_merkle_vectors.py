"""Regression tests for the TAS v1 SHA-256 Merkle conformance artifacts."""

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "tas-conformance-v1.json"
VECTORS_PATH = REPOSITORY_ROOT / "conformance-tests" / "merkle" / "vectors_v1_sha256.json"
ERROR_CODES_PATH = REPOSITORY_ROOT / "conformance-tests" / "error_codes_v1.json"


def _load_json(path: Path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_levels(leaf_hashes: list[str], node_header: bytes) -> list[list[str]]:
    levels = [leaf_hashes]
    current = leaf_hashes
    while len(current) > 1:
        parents = [
            _sha256_hex(node_header + bytes.fromhex(current[index]) + bytes.fromhex(current[index + 1]))
            for index in range(0, len(current) - 1, 2)
        ]
        if len(current) % 2:
            parents.append(current[-1])
        levels.append(parents)
        current = parents
    return levels


def test_manifest_hash_is_jcs_sha256_with_its_hash_field_omitted():
    manifest = _load_json(MANIFEST_PATH)
    expected_hash = manifest.pop("suite_sha256")

    assert _sha256_hex(_canonical_json(manifest)) == expected_hash


def test_manifest_lists_the_merkle_vectors_once_and_in_order():
    manifest = _load_json(MANIFEST_PATH)
    vectors = _load_json(VECTORS_PATH)
    vector_ids = [vector["vector_id"] for vector in vectors]

    assert manifest["merkle_hash_algorithm"] == "SHA-256"
    assert manifest["merkle_odd_node_rule"] == "PROMOTE_UNCHANGED"
    assert manifest["merkle_leaf_ordering"] == "PRESERVE_INPUT_ORDER"
    assert manifest["vectors"][-len(vector_ids) :] == vector_ids
    assert len(vector_ids) == len(set(vector_ids))


def test_acceptance_vectors_match_leaf_node_and_promotion_rules():
    vectors = _load_json(VECTORS_PATH)

    empty_vector = vectors[0]
    assert empty_vector["leaves"] == []
    assert empty_vector["expected_levels"] == []
    assert _sha256_hex(bytes.fromhex(empty_vector["expected_empty_preimage_hex"])) == empty_vector[
        "expected_root_hash"
    ]

    for vector in vectors[1:5]:
        leaf_header = bytes.fromhex(vector["domain"]["leaf_header_hex"])
        node_header = bytes.fromhex(vector["domain"]["node_header_hex"])
        leaf_hashes = []
        for leaf in vector["leaves"]:
            canonical = _canonical_json(leaf["input"])
            assert canonical.hex() == leaf["expected_canonical_hex"]
            assert leaf_header + canonical == bytes.fromhex(leaf["expected_leaf_preimage_hex"])
            assert _sha256_hex(bytes.fromhex(leaf["expected_leaf_preimage_hex"])) == leaf[
                "expected_leaf_hash"
            ]
            leaf_hashes.append(leaf["expected_leaf_hash"])

        assert vector["odd_node_rule"] == "PROMOTE_UNCHANGED"
        assert vector["leaf_ordering"] == "PRESERVE_INPUT_ORDER"
        assert _build_levels(leaf_hashes, node_header) == vector["expected_levels"]
        assert vector["expected_levels"][-1][0] == vector["expected_root_hash"]


def test_invalid_vectors_report_root_mismatch_for_their_changed_inputs():
    vectors = _load_json(VECTORS_PATH)
    errors = _load_json(ERROR_CODES_PATH)["errors"]

    for vector in vectors[5:]:
        assert vector["expected_result"] == "REJECT"
        assert vector["expected_error"] == "ERR_MERKLE_ROOT_MISMATCH"
        assert vector["expected_error"] in errors
        assert vector["provided_root_hash"] != vector["actual_root_hash"]
