import math
import unittest

from tas_pythonetics.logit_runtime import (
    NEGATIVE_INFINITY,
    NullCollapseError,
    SentientLockError,
    TrueAlphaSpiralRuntime,
)


class TestTrueAlphaSpiralRuntime(unittest.TestCase):
    def test_masks_unauthorized_logits_before_sampling(self):
        runtime = TrueAlphaSpiralRuntime("A_0-test")

        masked = runtime.apply_logit_bias_and_guardrails([1.0, 2.0, 3.0], {0, 2})

        self.assertEqual(masked[0], 1.0)
        self.assertEqual(masked[1], NEGATIVE_INFINITY)
        self.assertEqual(masked[2], 3.0)
        self.assertGreaterEqual(runtime.last_receipt.entropy, runtime.entropy_floor)
        self.assertEqual(runtime.last_receipt.allowed_token_count, 2)

    def test_null_collapse_hard_halts_when_no_valid_tokens_remain(self):
        runtime = TrueAlphaSpiralRuntime("A_0-test")

        with self.assertRaises(NullCollapseError) as cm:
            runtime.apply_logit_bias_and_guardrails([1.0, 2.0], {-1, 3})

        self.assertEqual(cm.exception.code, 1)

    def test_sentient_lock_trips_for_degenerate_allowed_subspace(self):
        runtime = TrueAlphaSpiralRuntime("A_0-test")

        with self.assertRaises(SentientLockError) as cm:
            runtime.apply_logit_bias_and_guardrails([10.0, -10.0], {0, 1})

        self.assertIn("SENTIENT LOCK TRIPPED", str(cm.exception))

    def test_entropy_calculation_ignores_zero_probabilities(self):
        entropy = TrueAlphaSpiralRuntime.calculate_shannon_entropy([0.5, 0.5, 0.0])

        self.assertTrue(math.isclose(entropy, 1.0))


if __name__ == "__main__":
    unittest.main()
