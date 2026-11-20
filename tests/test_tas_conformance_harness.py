"""Tests for isolated primitives, not a protocol conformance runner."""

import hashlib
import random
import unittest
from fractions import Fraction

from tas_conformance_harness import (
    Allocation,
    CapabilityEnvelope,
    SettlementSlice,
    allocation_digest,
    calculate_batch_allocations,
    compute_jcs_receipt_digest,
    derive_capability_key_index,
    deterministic_jcs_serialize,
)


class KeyIndexTests(unittest.TestCase):
    def test_domain_and_length_prefixes(self):
        cap = CapabilityEnvelope("issuer", "cap", 90, 110)
        expected = hashlib.sha256(
            b"\x02\x00\x00\x00\x06issuer\x00\x00\x00\x03cap"
        ).hexdigest()
        self.assertEqual(derive_capability_key_index(cap), expected)
        self.assertNotEqual(
            derive_capability_key_index(CapabilityEnvelope("ab", "c", 0, 0)),
            derive_capability_key_index(CapabilityEnvelope("a", "bc", 0, 0)),
        )
        self.assertEqual(
            derive_capability_key_index(CapabilityEnvelope("é", "x", 0, 0)),
            hashlib.sha256(b"\x02\x00\x00\x00\x02\xc3\xa9\x00\x00\x00\x01x").hexdigest(),
        )

    def test_reject_invalid_key(self):
        for cap in (CapabilityEnvelope("\ud800", "cap", 0, 0),
                    CapabilityEnvelope("issuer", "", 0, 0)):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                derive_capability_key_index(cap)
        with self.assertRaises(TypeError):
            derive_capability_key_index({"issuer": "issuer"})


class ReceiptTests(unittest.TestCase):
    def test_receipt_digest_and_canonical_encoding(self):
        body = {"z": [True, None, "\n"], "a": 7}
        expected = b'{"a":7,"z":[true,null,"\\n"]}'
        self.assertEqual(deterministic_jcs_serialize(body), expected)
        self.assertEqual(compute_jcs_receipt_digest(body), hashlib.sha256(
            b"TAS\x00ADMISSIBILITY-RECEIPT\x00v1\x00" + expected).hexdigest())
        self.assertEqual(compute_jcs_receipt_digest(body),
                         compute_jcs_receipt_digest({"a": 7, "z": [True, None, "\n"]}))
        self.assertNotEqual(compute_jcs_receipt_digest(body),
                            compute_jcs_receipt_digest({"a": 8, "z": [True, None, "\n"]}))
        self.assertEqual(deterministic_jcs_serialize({"\ue000": 1, "\U00010000": 2}),
                         '{"𐀀":2,"\ue000":1}'.encode())

    def test_reject_unsupported_json(self):
        for value in (0.0, -0.0, float("inf"), float("nan"), {"x": [1.0]}):
            with self.subTest(value=value), self.assertRaises(TypeError):
                deterministic_jcs_serialize(value)
        for value in (2**53, -(2**53), "\ud800", {"\udfff": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                deterministic_jcs_serialize(value)
        for value in ({1: "not a JSON key"}, (1, 2), b"x"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                deterministic_jcs_serialize(value)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            deterministic_jcs_serialize(cycle)
        shared = [1]
        self.assertEqual(deterministic_jcs_serialize([shared, shared]), b"[[1],[1]]")


class SettlementMathTests(unittest.TestCase):
    def test_ties_and_zero(self):
        slices = [SettlementSlice("b", 5000), SettlementSlice("a", 5000)]
        self.assertEqual(calculate_batch_allocations(5, slices),
                         (Allocation("b", 2), Allocation("a", 3)))
        self.assertEqual(calculate_batch_allocations(0, slices),
                         (Allocation("b", 0), Allocation("a", 0)))
        self.assertEqual(calculate_batch_allocations(3, [SettlementSlice("a", 0),
                                                     SettlementSlice("b", 10000)]),
                         (Allocation("a", 0), Allocation("b", 3)))

    def test_invalid_inputs_and_overflow(self):
        valid = [SettlementSlice("a", 10000)]
        for pool, slices, error in (
            (10, [], ValueError),
            (10, [SettlementSlice("a", 9999)], ValueError),
            (-1, valid, ValueError),
            (True, valid, TypeError),
            (1, [SettlementSlice("a", True)], TypeError),
            (1, [SettlementSlice("a", -1)], ValueError),
            (1, [SettlementSlice("a", 10001)], ValueError),
            (1, [SettlementSlice("", 10000)], ValueError),
            (1, [{"artifact_id": "a", "bps": 10000}], TypeError),
            (1 << 64, valid, OverflowError),
            ((1 << 64) - 1, valid, OverflowError),
        ):
            with self.subTest(pool=pool, slices=slices), self.assertRaises(error):
                calculate_batch_allocations(pool, slices)

    def test_allocation_digest_is_normalized_cvp_jcs(self):
        allocations = (SettlementSlice("b", 4000), SettlementSlice("a", 6000))
        expected = b'[{"artifact_id":"b","bps":4000},{"artifact_id":"a","bps":6000}]'
        self.assertEqual(allocation_digest(allocations), hashlib.sha256(expected).hexdigest())
        self.assertNotEqual(allocation_digest(allocations), allocation_digest(allocations[::-1]))
        self.assertNotEqual(allocation_digest(allocations), allocation_digest(
            (SettlementSlice("a", 5000), SettlementSlice("b", 5000))))
        duplicates = (SettlementSlice("a", 7000), SettlementSlice("a", 3000))
        self.assertNotEqual(allocation_digest(duplicates), allocation_digest(duplicates[::-1]))
        for invalid in ([], [SettlementSlice("a", 9999)], [SettlementSlice("a", -1)],
                        [SettlementSlice("a", 10001)], [SettlementSlice("", 10000)]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                allocation_digest(invalid)
        with self.assertRaises(TypeError):
            allocation_digest([{"artifact_id": "a", "bps": 10000}])
        with self.assertRaises(TypeError):
            allocation_digest([SettlementSlice("a", 10000.0)])

    def test_deterministic_1000_trials(self):
        rng = random.Random(20261120)
        for trial in range(1000):
            pool = rng.randrange(100000)
            count = rng.randrange(1, 16)
            cuts = [0] + sorted(rng.randrange(10001) for _ in range(count - 1)) + [10000]
            slices = [SettlementSlice(f"id-{i:02}", cuts[i + 1] - cuts[i])
                      for i in range(count)]
            quotas = {s.artifact_id: Fraction(pool * s.bps, 10000) for s in slices}
            amounts = {name: q.numerator // q.denominator for name, q in quotas.items()}
            order = sorted(quotas, key=lambda name: (-(quotas[name] - amounts[name]), name))
            for name in order[:pool - sum(amounts.values())]:
                amounts[name] += 1
            with self.subTest(trial=trial):
                result = calculate_batch_allocations(pool, slices)
                self.assertEqual({a.artifact_id: a.amount for a in result}, amounts)
                self.assertEqual(sum(a.amount for a in result), pool)
                reverse = calculate_batch_allocations(pool, list(reversed(slices)))
                self.assertEqual({a.artifact_id: a.amount for a in reverse}, amounts)


if __name__ == "__main__":
    unittest.main()
