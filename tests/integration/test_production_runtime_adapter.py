"""Contract tests for the production JSON-RPC boundary, including OCC behavior."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "production_runtime.py"
ADAPTER = ROOT / "bin" / "runtime_adapter"


def receipt(key: Ed25519PrivateKey, receipt_id: str = "r-1") -> dict[str, object]:
    value: dict[str, object] = {
        "id": receipt_id,
        "candidate_hash": "sha256:candidate",
        "context_hash": "sha256:context",
        "decision": "ADMITTED",
        "credential_id": "verifier-1",
        "invariant_results": {"schema": True, "bounds": True},
    }
    value["signature"] = key.sign(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hex()
    return value


def start_runtime(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "verifier.hex"
    key_path.write_text(key.public_key().public_bytes_raw().hex(), encoding="ascii")
    socket = tmp_path / "runtime.sock"
    process = subprocess.Popen([sys.executable, str(RUNTIME), "--socket-path", str(socket), "--public-key-file", str(key_path), "--ephemeral"], cwd=ROOT)
    for _ in range(100):
        if socket.exists():
            return key, socket, process
        time.sleep(.02)
    process.kill()
    raise AssertionError("runtime did not become ready")


def adapter(socket: Path, action: str, fixture: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    command = [str(ADAPTER), "client", action, "--socket", str(socket)]
    if action == "verify-receipt":
        command += ["--input", str(fixture)]
    elif action == "submit":
        command += ["--payload", str(fixture)]
    else:
        assert extra
        command += extra
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def test_signed_receipt_is_required_and_stale_commit_preserves_competitor(tmp_path: Path) -> None:
    key, socket, process = start_runtime(tmp_path)
    try:
        signed = tmp_path / "signed.json"
        signed.write_text(json.dumps(receipt(key)), encoding="utf-8")
        assert adapter(socket, "verify-receipt", signed).returncode == 0

        unsigned = tmp_path / "unsigned.json"
        unsigned.write_text(json.dumps({"id": "broken"}), encoding="utf-8")
        rejected = adapter(socket, "submit", unsigned)
        assert rejected.returncode == 0
        assert json.loads(rejected.stdout)["status"] == "REJECTED"

        empty_invariants = tmp_path / "empty-invariants.json"
        invalid = receipt(key, "empty-invariants")
        invalid["invariant_results"] = {}
        # The old signature no longer covers this changed payload, and an empty
        # invariant set is independently invalid as well.
        empty_invariants.write_text(json.dumps({"receipt": invalid}), encoding="utf-8")
        assert json.loads(adapter(socket, "submit", empty_invariants).stdout)["status"] == "REJECTED"

        fresh, stale = tmp_path / "fresh.json", tmp_path / "stale.json"
        fresh.write_text(json.dumps({"read_version": 0, "receipt": receipt(key, "fresh")}), encoding="utf-8")
        stale.write_text(json.dumps({"read_version": 0, "receipt": receipt(key, "stale")}), encoding="utf-8")
        raced = adapter(socket, "run-race", fresh, ["--competing-tx", str(fresh), "--stale-tx", str(stale)])
        assert raced.returncode == 0, raced.stderr
        assert json.loads(raced.stdout) == {"competing_committed": True, "conflict_code": "ERR_OCC_STALE_READ", "stale_rejected": True}
    finally:
        process.terminate()
        process.wait(timeout=5)
