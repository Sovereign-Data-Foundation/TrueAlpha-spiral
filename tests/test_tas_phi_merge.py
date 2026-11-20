import hashlib
import itertools
import random
import unittest
from dataclasses import replace

from tas_conformance_harness import SettlementSlice, allocation_digest
from tas_phi_merge import (
    DischargeProof,
    ExclusiveLock,
    MergeResult,
    Obligation,
    ParentArtifact,
    merge,
)


def parent(name="a", time=1, authority=7, obligations=(), raw=1):
    return ParentArtifact(name, time, authority, obligations, raw)


class PhiMergeTests(unittest.TestCase):
    def setUp(self):
        self.sticky = Obligation("sticky", "sticky")
        self.due = Obligation("due", "dischargeable", "receipt", "digest")
        self.proof = DischargeProof("due", "receipt", "digest", True)

    def test_meet_union_normalization_order_and_digest(self):
        parents = [
            parent("z", 1, 0b1110, (self.sticky, self.due), 1),
            parent("b", 1, 0b1101, (self.sticky,), 1),
            parent("a", 0, 0b1011, (), 1),
        ]
        result = merge(parents)
        self.assertIsInstance(result, MergeResult)
        self.assertEqual(result.authorityU, 0b1000)
        self.assertEqual(result.obligations, (self.due, self.sticky))
        self.assertEqual(result.allocations, (
            SettlementSlice("a", 3334), SettlementSlice("b", 3333),
            SettlementSlice("z", 3333)))
        self.assertEqual(result.allocation_digest, allocation_digest(result.allocations))
        self.assertEqual(result.allocation_digest, hashlib.sha256(
            b'[{"artifact_id":"a","bps":3334},{"artifact_id":"b","bps":3333},'
            b'{"artifact_id":"z","bps":3333}]').hexdigest())
        for permutation in itertools.permutations(parents):
            self.assertEqual(merge(permutation), result)

    def test_remainder_all_goes_to_earliest_not_largest_fraction(self):
        result = merge([parent("z", 5, raw=1), parent("b", 1, raw=2),
                        parent("a", 1, raw=3), parent("d", 3, raw=1),
                        parent("c", 2, raw=1), parent("e", 4, raw=1)])
        self.assertEqual(result.allocations, (
            SettlementSlice("a", 3334), SettlementSlice("b", 2222),
            SettlementSlice("c", 1111), SettlementSlice("d", 1111),
            SettlementSlice("e", 1111), SettlementSlice("z", 1111)))
        equal = merge([parent(str(i), i) for i in range(6)])
        self.assertEqual([item.bps for item in equal.allocations],
                         [1670, 1666, 1666, 1666, 1666, 1666])

    def test_zero_weight_and_large_integer_normalization(self):
        result = merge([parent("zero", 0, raw=0),
                        parent("big", 1, raw=10**100),
                        parent("tiny", 2, raw=1)])
        self.assertEqual(result.allocations, (
            SettlementSlice("zero", 1), SettlementSlice("big", 9999),
            SettlementSlice("tiny", 0)))

    def test_verified_discharge_and_sticky_propagation(self):
        calls = []

        def verifier(obligation, proof):
            calls.append((obligation, proof))
            return True

        result = merge([parent(obligations=(self.due, self.sticky))],
                       [self.proof], verifier=verifier)
        self.assertEqual(result.obligations, (self.sticky,))
        self.assertEqual(calls, [(self.due, self.proof)])
        self.assertEqual(merge([parent(obligations=(self.due,))]).obligations,
                         (self.due,))

    def test_proof_cannot_discharge_without_independent_verification(self):
        parents = [parent(obligations=(self.due,))]
        for verifier in (None, lambda *_: False, lambda *_: 1, lambda *_: None):
            with self.subTest(verifier=verifier), self.assertRaises(ValueError):
                merge(parents, [self.proof], verifier=verifier)

        def broken(*_):
            raise RuntimeError("unavailable")

        with self.assertRaises(ValueError):
            merge(parents, [self.proof], verifier=broken)
        with self.assertRaises(TypeError):
            merge(parents, [self.proof], verifier=True)

    def test_wrong_or_unmatched_proofs_fail_closed(self):
        parents = [parent(obligations=(self.due, self.sticky))]
        invalid = (
            replace(self.proof, obligationId="missing"),
            replace(self.proof, obligationId="sticky"),
            replace(self.proof, proofType="wrong"),
            replace(self.proof, attestationDigest="wrong"),
            replace(self.proof, signatureValid=False),
        )
        for proof in invalid:
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                merge(parents, [proof], verifier=lambda *_: True)
        with self.assertRaises(TypeError):
            merge(parents, [replace(self.proof, signatureValid=1)],
                  verifier=lambda *_: True)
        with self.assertRaises(ValueError):
            merge(parents, [self.proof, self.proof], verifier=lambda *_: True)

    def test_proof_verification_order_is_deterministic(self):
        first = Obligation("a", "dischargeable", "x", "y")
        last = Obligation("z", "dischargeable", "x", "y")
        proofs = [DischargeProof("z", "x", "y", True),
                  DischargeProof("a", "x", "y", True)]
        calls = []
        result = merge([parent(obligations=(last, first))], proofs,
                       verifier=lambda obligation, proof: calls.append(proof.obligationId) or True)
        self.assertEqual(calls, ["a", "z"])
        self.assertEqual(result.obligations, ())

    def test_active_locks_conflict_only_after_discharge(self):
        a = Obligation("a", "sticky", exclusiveLock=ExclusiveLock("k", "v1"))
        b = Obligation("b", "dischargeable", "type", "digest",
                       ExclusiveLock("k", "v2"))
        c = Obligation("c", "sticky", exclusiveLock=ExclusiveLock("k", "v1"))
        d = Obligation("d", "sticky", exclusiveLock=ExclusiveLock("other", "v2"))
        parents = [parent(obligations=(a, b, c, d))]
        with self.assertRaisesRegex(ValueError, "INCOMPATIBLE_LINEAGE_MERGE"):
            merge(parents)
        result = merge(parents, [DischargeProof("b", "type", "digest", True)],
                       verifier=lambda *_: True)
        self.assertEqual(result.obligations, (a, c, d))

    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):
            merge([parent("same"), parent("same")])
        self.assertEqual(merge([parent("a", obligations=(self.sticky,)),
                                parent("b", obligations=(self.sticky,))]).obligations,
                         (self.sticky,))
        with self.assertRaises(ValueError):
            merge([parent("a", obligations=(self.sticky,)),
                   parent("b", obligations=(Obligation("sticky", "dischargeable",
                                                       "type", "digest"),))])

    def test_zero_authority_meet_has_incompatible_lineage_code(self):
        for parents in ([parent(authority=0)],
                        [parent("a", authority=1), parent("b", authority=2)]):
            with self.subTest(parents=parents):
                with self.assertRaisesRegex(ValueError, "INCOMPATIBLE_LINEAGE_MERGE"):
                    merge(parents)

    def test_bad_parents(self):
        invalid_parents = (
            [], (), [parent(authority=0)],
            [parent("a", authority=1), parent("b", authority=2)],
            [parent(raw=0)], [parent(name="")], [parent(name="\ud800")],
            [parent(time=-1)], [parent(time=True)], [parent(time=1.0)],
            [parent(authority=-1)], [parent(authority=True)],
            [parent(raw=-1)], [parent(raw=True)], [parent(raw=1.0)],
            [parent(obligations=None)], [parent(obligations=(object(),))],
            [object()], None, "parents",
        )
        for value in invalid_parents:
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                merge(value)

    def test_bad_obligations_and_proofs(self):
        invalid = (
            Obligation("", "sticky"), Obligation("a", "unknown"),
            Obligation("a", "sticky", "type", "digest"),
            Obligation("a", "dischargeable"),
            Obligation("a", "dischargeable", "type", ""),
            Obligation("a", "sticky", exclusiveLock=ExclusiveLock("", "value")),
            Obligation("a", "sticky", exclusiveLock=ExclusiveLock("key", "")),
            Obligation("a", "sticky", exclusiveLock="lock"),
        )
        for obligation in invalid:
            with self.subTest(obligation=obligation), self.assertRaises((TypeError, ValueError)):
                merge([parent(obligations=(obligation,))])
        for proofs in (None, "proofs", [object()],
                       [replace(self.proof, proofType="")],
                       [replace(self.proof, attestationDigest="\ud800")]):
            with self.subTest(proofs=proofs), self.assertRaises((TypeError, ValueError)):
                merge([parent(obligations=(self.due,))], proofs, verifier=lambda *_: True)

    def test_random_permutations_preserve_result_and_invariants(self):
        rng = random.Random(20261120)
        for _ in range(100):
            parents = [parent(str(i), rng.randrange(3), rng.randrange(1, 256) | 1,
                              raw=rng.randrange(100)) for i in range(10)]
            expected = merge(parents)
            rng.shuffle(parents)
            self.assertEqual(merge(parents), expected)
            self.assertEqual(sum(item.bps for item in expected.allocations), 10000)
            self.assertTrue(expected.authorityU & 1)


if __name__ == "__main__":
    unittest.main()
