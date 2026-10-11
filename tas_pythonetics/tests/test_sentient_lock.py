import unittest
from unittest.mock import patch, MagicMock
from tas_pythonetics.sentient_lock import verify_kinematic_identity, PhoenixError, TAS_KINEMATIC_PREFIX

class TestSentientLock(unittest.TestCase):

    def test_verify_kinematic_identity_pass(self):
        # Mock sha256 to return a hash starting with the correct prefix
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = TAS_KINEMATIC_PREFIX + "abcdef1234567890"

        with patch('hashlib.sha256', return_value=mock_hash):
            result = verify_kinematic_identity("valid_data")
            self.assertTrue(result)

    def test_verify_kinematic_identity_fail(self):
        # Mock sha256 to return a hash with incorrect prefix
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = "0000abcdef123456" # Not 1618

        with patch('hashlib.sha256', return_value=mock_hash):
            with self.assertRaises(PhoenixError) as cm:
                verify_kinematic_identity("invalid_data")
            self.assertIn("Expected prefix '1618'", str(cm.exception))

    def test_verify_kinematic_identity_signature(self):
        # Ensure signature is used in payload
        # We can't easily check the input to sha256 with a simple patch on the result,
        # but we can patch hashlib.sha256 and check call args.

        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = TAS_KINEMATIC_PREFIX + "valid"

        with patch('hashlib.sha256', return_value=mock_hash) as mock_sha256:
            verify_kinematic_identity("data", signature="TEST_SIG")

            # Verify called with data + signature
            expected_payload = "dataTEST_SIG".encode()
            mock_sha256.assert_called_with(expected_payload)


class TestSentientLockHmacGate(unittest.TestCase):

    def _signature(self, key, state):
        import hashlib
        import hmac
        return hmac.new(key, state.encode("utf-8"), hashlib.sha256).hexdigest()

    def test_valid_hmac_transition_commits_to_disk(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tas_pythonetics.sentient_lock import SentientLock

        key = b"father-day-anchor"
        state = "verified structural update"
        ledger = []

        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "verified.txt"
            lock = SentientLock(key, ledger)
            result = lock.attempt_state_transition(state, self._signature(key, state), target)

            self.assertIn("State Transition Verified", result)
            self.assertEqual(target.read_text(encoding="utf-8"), state)
            self.assertTrue(lock.compute_active)
            self.assertEqual(ledger, [])

    def test_malformed_hmac_inputs_engage_lock_without_exception(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tas_pythonetics.sentient_lock import SentientLock

        ledger = []
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "blocked.txt"
            lock = SentientLock(b"father-day-anchor", ledger)
            result = lock.attempt_state_transition(None, ["not", "a", "signature"], target)

            self.assertEqual(result, "Verification Failed: Sentient Lock Engaged")
            self.assertFalse(lock.compute_active)
            self.assertFalse(target.exists())
            self.assertEqual(ledger[0]["event"], "HALLUCINATION_CASCADE_DETECTED")
            self.assertEqual(ledger[0]["failed_target"], str(target))
            self.assertIsNone(ledger[0]["invalid_state_dump"])

    def test_compute_starvation_blocks_follow_on_transition(self):
        from tas_pythonetics.sentient_lock import SentientLock

        lock = SentientLock(b"father-day-anchor", [])
        lock.attempt_state_transition("state", "bad-signature", "blocked.txt")

        self.assertEqual(
            lock.attempt_state_transition("state", "bad-signature", "blocked.txt"),
            "Transition Blocked: Compute Starved",
        )


if __name__ == '__main__':
    unittest.main()
