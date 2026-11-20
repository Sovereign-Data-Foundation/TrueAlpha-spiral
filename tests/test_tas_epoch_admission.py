"""Tests for independently configured epoch and sparse-tree admission."""

import hashlib
import unittest
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tas_conformance_harness import (
    CapabilityEnvelope,
    _RECEIPT_DOMAIN,
    derive_capability_key_index,
    deterministic_jcs_serialize,
)
from tas_epoch_admission import (
    SUITE,
    AdmissionEvidence,
    GateStatus as Status,
    Epoch,
    SparseProof,
    TrustedEpoch,
    _proof_root,
    epoch_signing_payload,
    evaluate_epoch_admission,
    sign_epoch,
)


def root_for(index, leaf, siblings):
    index_bytes = bytes.fromhex(index)
    leaf_bytes = bytes.fromhex(leaf)
    node = (bytes(32) if leaf_bytes == bytes(32)
            else hashlib.sha256(b"\x00" + index_bytes + leaf_bytes).digest())
    path = int(index, 16)
    for level, sibling_hex in enumerate(siblings):
        sibling = bytes.fromhex(sibling_hex)
        node = hashlib.sha256(
            b"\x01" + (sibling + node if (path >> level) & 1 else node + sibling)
        ).digest()
    return node.hex()


class EpochAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
        pub = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.cap = CapabilityEnvelope("issuer", "capability", 0, 1000)
        self.siblings = tuple(
            hashlib.sha256(("sibling-" + str(i)).encode()).hexdigest()
            for i in range(256)
        )
        self.proof = SparseProof(
            derive_capability_key_index(self.cap), "00" * 32, self.siblings
        )
        root = root_for(self.proof.index, self.proof.leaf, self.siblings)
        self.epoch = Epoch(7, "issuer", 100, 200, root, SUITE, 50)
        self.trust = TrustedEpoch("issuer", pub, 7, root)
        self.evidence = AdmissionEvidence(
            self.epoch, sign_epoch(self.epoch, self.key), self.cap, self.proof
        )

    def evaluate(self, evidence=None, trusted=None, now=125, cached_age=0):
        return evaluate_epoch_admission(
            self.evidence if evidence is None else evidence,
            trusted=self.trust if trusted is None else trusted,
            now=now, cached_age=cached_age
        )

    def signed(self, epoch):
        return replace(self.evidence, epoch=epoch, signature=sign_epoch(epoch, self.key))

    def test_signing_payload_is_complete_canonical_and_domain_prefixed(self):
        self.assertEqual(SUITE, "OURSPACE-SMT-SHA256-V1")
        expected = {
            "epoch": 7, "issuer": "issuer", "valid_from": 100,
            "valid_until": 200, "root": self.epoch.root, "suite": SUITE,
            "max_freshness_seconds": 50,
        }
        self.assertEqual(epoch_signing_payload(self.epoch),
                         _RECEIPT_DOMAIN + deterministic_jcs_serialize(expected))
        self.key.public_key().verify(sign_epoch(self.epoch, self.key),
                                     epoch_signing_payload(self.epoch))

    def test_verified_and_revoked_with_real_proofs(self):
        self.assertEqual(self.evaluate(), Status.VERIFIED)
        leaf = "ff" * 32
        proof = replace(self.proof, leaf=leaf)
        root = root_for(proof.index, leaf, proof.siblings)
        epoch = replace(self.epoch, root=root)
        evidence = replace(self.signed(epoch), proof=proof)
        trust = replace(self.trust, root=root)
        self.assertEqual(self.evaluate(evidence, trust), Status.REVOKED)
        self.assertEqual(self.evaluate(replace(evidence, proof=replace(
            proof, leaf="ee" * 32)), trust), Status.INVALID)
        self.assertEqual(self.evaluate(replace(evidence, proof=replace(
            proof, siblings=("ff" * 32,) + proof.siblings[1:])), trust),
            Status.INVALID)

    def test_nonzero_leaf_fixed_vector_and_both_path_ends(self):
        proof = SparseProof(
            "80" + "00" * 30 + "01", "ab" * 32,
            tuple(hashlib.sha256(i.to_bytes(2, "big")).hexdigest()
                  for i in range(256)),
        )
        self.assertEqual(_proof_root(proof).hex(),
                         "c0a01c3c0da02e7b59fc6d671a93d605"
                         "69e99f5b6372150cd7f790a6f26050cc")

    def test_missing_and_authority_precedence(self):
        self.assertEqual(evaluate_epoch_admission(None, trusted=None, now=0,
                                                   cached_age=0),
                         Status.UNVERIFIED)
        for field in ("epoch", "signature", "capability", "proof"):
            evidence = replace(self.evidence, **{field: None})
            self.assertEqual(evaluate_epoch_admission(evidence, trusted=None, now=0,
                                                       cached_age=0),
                             Status.UNVERIFIED)
        for trust in (None, True, replace(self.trust, issuer_key=b""),
                      replace(self.trust, root="00"),
                      replace(self.trust, minimum_epoch=True)):
            self.assertEqual(evaluate_epoch_admission(
                replace(self.evidence, signature=b""), trusted=trust, now=0,
                cached_age=0
            ), Status.INDETERMINATE)

    def test_all_signed_fields_are_authenticated(self):
        changes = {
            "epoch": 8, "issuer": "other", "valid_from": 99,
            "valid_until": 201, "root": "11" * 32, "suite": "other",
            "max_freshness_seconds": 51,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                evidence = replace(self.evidence, epoch=replace(self.epoch, **{field: value}))
                self.assertEqual(self.evaluate(evidence), Status.INVALID)

    def test_bad_signature_suite_epoch_and_issuer_precede_expiry(self):
        for sig in (b"", b"\x00" * 64, b"a" * 63, True,
                    Ed25519PrivateKey.generate().sign(epoch_signing_payload(self.epoch))):
            self.assertEqual(self.evaluate(replace(self.evidence, signature=sig), now=999),
                             Status.INVALID)
        for change in ({"suite": "other"}, {"epoch": 6}, {"issuer": "other"}):
            self.assertEqual(self.evaluate(self.signed(replace(self.epoch, **change)),
                                           now=999), Status.INVALID)
        self.assertEqual(self.evaluate(trusted=replace(
            self.trust, issuer_key=Ed25519PrivateKey.generate().public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ))), Status.INVALID)

    def test_epoch_validation_and_jcs_integer_limits(self):
        for field, value in (
            ("epoch", True), ("epoch", -1), ("epoch", 1 << 53),
            ("issuer", ""), ("issuer", "\ud800"), ("valid_from", 201),
            ("valid_until", -1), ("valid_until", 1.0), ("root", ""),
            ("suite", ""), ("max_freshness_seconds", -1),
            ("max_freshness_seconds", True),
        ):
            with self.subTest(field=field, value=value):
                epoch = replace(self.epoch, **{field: value})
                self.assertEqual(self.evaluate(replace(self.evidence, epoch=epoch)),
                                 Status.INVALID)
                with self.assertRaises((ValueError, TypeError)):
                    epoch_signing_payload(epoch)

    def test_time_and_cache_expiry_and_boundaries(self):
        with self.assertRaises(TypeError):
            evaluate_epoch_admission(self.evidence, trusted=self.trust, now=125)
        for now in (100, 150, 200):
            self.assertEqual(self.evaluate(now=now, cached_age=50), Status.VERIFIED)
        for now in (99, 201, -1, True, 125.0):
            self.assertEqual(self.evaluate(now=now), Status.EXPIRED)
        for age in (51, -1, True, 0.1, None):
            self.assertEqual(self.evaluate(cached_age=age), Status.EXPIRED)
        self.assertEqual(self.evaluate(now=151, cached_age=0), Status.VERIFIED)
        epoch = replace(self.epoch, max_freshness_seconds=100)
        self.assertEqual(self.evaluate(self.signed(epoch), now=200), Status.VERIFIED)
        self.assertEqual(self.evaluate(self.signed(epoch), now=201), Status.EXPIRED)
        epoch = replace(self.epoch, max_freshness_seconds=0)
        self.assertEqual(self.evaluate(self.signed(epoch), now=100), Status.VERIFIED)
        self.assertEqual(self.evaluate(self.signed(epoch), now=101), Status.VERIFIED)
        self.assertEqual(self.evaluate(self.signed(epoch), now=101, cached_age=1),
                         Status.EXPIRED)

    def test_epoch_minimum_and_capability_validity(self):
        for epoch_number, result in ((6, Status.INVALID), (7, Status.VERIFIED),
                                     (8, Status.VERIFIED)):
            self.assertEqual(self.evaluate(self.signed(replace(
                self.epoch, epoch=epoch_number))), result)
        cap = replace(self.cap, valid_from=110, valid_until=130)
        evidence = replace(self.evidence, capability=cap)
        for now in (110, 130):
            self.assertEqual(self.evaluate(evidence, now=now), Status.VERIFIED)
        for now in (109, 131):
            self.assertEqual(self.evaluate(replace(evidence, proof=True), now=now),
                             Status.EXPIRED)
        for start, end in ((-1, 1000), (True, 1000), (0, 1 << 53), (126, 125)):
            self.assertEqual(self.evaluate(replace(
                self.evidence, capability=replace(self.cap, valid_from=start,
                                                   valid_until=end)
            )), Status.INVALID)

    def test_statuses_are_numeric_but_cannot_be_used_as_booleans(self):
        self.assertEqual({status.name: status.value for status in Status}, {
            "VERIFIED": 2000, "INVALID": 4101, "UNVERIFIED": 4102,
            "REVOKED": 4103, "EXPIRED": 4104, "INDETERMINATE": 4105,
        })
        for status in Status:
            with self.assertRaises(TypeError):
                bool(status)

    def test_invalid_proofs_and_roots_follow_expiry(self):
        bad_proofs = [
            True,
            replace(self.proof, index="ff" * 32),
            replace(self.proof, index=self.proof.index.upper()),
            replace(self.proof, leaf=""),
            replace(self.proof, leaf="00" * 31),
            replace(self.proof, leaf=True),
            replace(self.proof, siblings=self.siblings[:-1]),
            replace(self.proof, siblings=self.siblings + ("00" * 32,)),
            replace(self.proof, siblings=list(self.siblings)),
            replace(self.proof, siblings=("00" * 31,) + self.siblings[1:]),
            replace(self.proof, siblings=("FF" * 32,) + self.siblings[1:]),
            replace(self.proof, siblings=(True,) + self.siblings[1:]),
            replace(self.proof, siblings=("00" * 32,) + self.siblings[1:]),
        ]
        for proof in bad_proofs:
            with self.subTest(proof=proof):
                evidence = replace(self.evidence, proof=proof)
                self.assertEqual(self.evaluate(evidence), Status.INVALID)
                self.assertEqual(self.evaluate(evidence, now=201), Status.EXPIRED)
        for root in ("ff" * 32, "0" * 63, "AA" * 32):
            evidence = self.signed(replace(self.epoch, root=root))
            self.assertEqual(self.evaluate(evidence), Status.INVALID)
            self.assertEqual(self.evaluate(evidence, now=201), Status.EXPIRED)
        self.assertEqual(self.evaluate(trusted=replace(self.trust, root="ff" * 32)),
                         Status.INVALID)
        self.assertEqual(self.evaluate(replace(
            self.evidence, capability=replace(self.cap, capability_id="different")
        )), Status.INVALID)
        self.assertEqual(self.evaluate(replace(
            self.evidence, capability=replace(self.cap, issuer="different")
        )), Status.INVALID)


if __name__ == "__main__":
    unittest.main()
