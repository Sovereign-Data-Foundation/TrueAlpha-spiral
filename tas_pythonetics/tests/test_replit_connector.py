import json
import unittest

from tas_pythonetics.replit_connector import (
    ReplitConnector,
    SovereignStructuralViolation,
    canonical_manifest_hash,
    character_shannon_entropy,
    structural_density,
)


class TestReplitConnector(unittest.TestCase):
    def test_canonical_manifest_hash_is_order_independent(self):
        first = {"workspace": "tas", "threads": ["gold", "teal", "violet"]}
        second = {"threads": ["gold", "teal", "violet"], "workspace": "tas"}

        self.assertEqual(canonical_manifest_hash(first), canonical_manifest_hash(second))

    def test_entropy_and_density_detect_repetition(self):
        dense = "Run tests, compile receipts, and block unsafe Replit workspace mutations."
        padded = "a" * 200

        self.assertGreater(character_shannon_entropy(dense), character_shannon_entropy(padded))
        self.assertGreater(structural_density(dense), 0.15)
        self.assertLess(structural_density(padded), 0.15)

    def test_verify_admits_dense_payload_with_matching_manifest(self):
        manifest = {"workspace": "tas", "threads": ["gold", "teal", "violet"]}
        connector = ReplitConnector()

        receipt = connector.verify(
            "Replit connector validates TAS receipts before workspace mutation.",
            manifest,
            canonical_manifest_hash(manifest),
        )

        self.assertTrue(receipt.admitted)
        self.assertEqual(receipt.reason, "admitted")
        self.assertEqual(receipt.connector, "replit")
        self.assertFalse(receipt.locked)
        self.assertEqual(receipt.expected_manifest_sha256, canonical_manifest_hash(manifest))

    def test_verify_locks_on_diluted_payload(self):
        manifest = {"workspace": "tas"}
        connector = ReplitConnector()

        with self.assertRaises(SovereignStructuralViolation) as cm:
            connector.verify("loop " * 100, manifest, canonical_manifest_hash(manifest))

        receipt = json.loads(str(cm.exception))
        self.assertFalse(receipt["admitted"])
        self.assertEqual(receipt["reason"], "density_below_threshold")
        self.assertTrue(receipt["locked"])
        self.assertTrue(connector.locked)
        self.assertEqual(len(connector.witness_receipts), 1)

    def test_verify_locks_on_manifest_mismatch(self):
        connector = ReplitConnector()

        with self.assertRaises(SovereignStructuralViolation) as cm:
            connector.verify("Dense Replit mutation request with enough structure.", {"workspace": "tas"}, "0" * 64)

        receipt = json.loads(str(cm.exception))
        self.assertFalse(receipt["admitted"])
        self.assertEqual(receipt["reason"], "manifest_hash_mismatch")
        self.assertTrue(receipt["locked"])
        self.assertEqual(receipt["expected_manifest_sha256"], "0" * 64)

    def test_sentient_lock_is_irreversible_after_failure(self):
        manifest = {"workspace": "tas"}
        connector = ReplitConnector()

        with self.assertRaises(SovereignStructuralViolation):
            connector.verify("loop " * 100, manifest, canonical_manifest_hash(manifest))

        with self.assertRaises(SovereignStructuralViolation) as cm:
            connector.verify(
                "Dense recovery attempt must not bypass the frozen connector context.",
                manifest,
                canonical_manifest_hash(manifest),
            )

        receipt = json.loads(str(cm.exception))
        self.assertEqual(receipt["reason"], "connector_locked")
        self.assertTrue(receipt["locked"])
        self.assertEqual(len(connector.witness_receipts), 1)


if __name__ == "__main__":
    unittest.main()
