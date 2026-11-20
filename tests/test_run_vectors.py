import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run_vectors


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads(run_vectors.DEFAULT_VECTORS.read_text(encoding="utf-8"))

    def run_data(self, data, args=(), returncode=0, error=None):
        source = data if isinstance(data, str) else json.dumps(data)
        with patch("sys.argv", ["run_vectors.py", *args]), \
             patch.object(Path, "open", autospec=True, return_value=io.StringIO(source)) as opened, \
             patch("run_vectors.subprocess.run", side_effect=error) as lean, \
             redirect_stdout(io.StringIO()):
            lean.return_value.returncode = returncode
            run_vectors.main()
            return opened, lean

    def test_default_and_explicit_paths_are_identical_for_both_runners(self):
        for args, expected in (((), run_vectors.DEFAULT_VECTORS),
                               (("tas_vectors_v0_7_0.json",), run_vectors.DEFAULT_VECTORS),
                               (("other.json",), run_vectors.ROOT / "other.json")):
            with self.subTest(args=args):
                opened, lean = self.run_data(self.vectors, args)
                self.assertEqual(opened.call_args.args[0], expected)
                lean.assert_called_once_with(
                    ["lake", "exe", "conformance", str(expected)],
                    cwd=run_vectors.ROOT, check=False,
                )

    def test_default_is_independent_of_cwd(self):
        with patch("os.getcwd", return_value="/"):
            _, lean = self.run_data(self.vectors)
        self.assertEqual(lean.call_args.args[0][-1], str(run_vectors.DEFAULT_VECTORS))

    def test_lean_failure_and_missing_executable_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "exit code 42"):
            self.run_data(self.vectors, returncode=42)
        with self.assertRaises(FileNotFoundError):
            self.run_data(self.vectors, error=FileNotFoundError("lake"))

    def test_missing_empty_malformed_and_unsupported_families_fail(self):
        for family in ("settlement", "uint64_ledger"):
            for value in (None, [], {}):
                data = copy.deepcopy(self.vectors)
                data["families"][family] = value
                with self.subTest(family=family, value=value), self.assertRaises(ValueError):
                    self.run_data(data)
            data = copy.deepcopy(self.vectors)
            del data["families"][family]
            with self.subTest(missing=family), self.assertRaisesRegex(ValueError, "missing required"):
                self.run_data(data)
        for families in ({}, {"other": []},
                         {**self.vectors["families"], "other": []}):
            data = {"version": "0.7.0", "families": families}
            with self.subTest(families=families.keys()), self.assertRaises(ValueError):
                self.run_data(data)

    def test_duplicate_keys_and_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.run_data('{"version":"0.7.0","version":"0.7.0","families":{}}')
        nested = json.dumps(self.vectors).replace('"pool": 3', '"pool": 3, "pool": 3', 1)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.run_data(nested)
        for family in self.vectors["families"]:
            data = copy.deepcopy(self.vectors)
            data["families"][family].append(copy.deepcopy(data["families"][family][0]))
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, "duplicate vector id"):
                self.run_data(data)
        data = copy.deepcopy(self.vectors)
        data["families"]["uint64_ledger"][0]["id"] = data["families"]["settlement"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate vector id"):
            self.run_data(data)

    def test_both_arithmetic_families_are_checked_before_lean(self):
        for family in self.vectors["families"]:
            data = copy.deepcopy(self.vectors)
            vector = data["families"][family][0]
            if family == "settlement":
                vector["expected"]["legal_reserve"] = 1
            else:
                vector["expected"] = not vector["expected"]
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, family):
                self.run_data(data)


if __name__ == "__main__":
    unittest.main()
