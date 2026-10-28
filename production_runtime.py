#!/usr/bin/env python3
"""Fail-closed JSON-RPC production verification runtime.

The process exposes only the RPC methods consumed by ``bin/runtime_adapter``.
It deliberately has no "allow unverified" mode: every executable benchmark or
transaction must carry an Ed25519-signed receipt from the configured trust root.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_MESSAGE = 8 * 1024 * 1024
RECEIPT_FIELDS = frozenset({"id", "candidate_hash", "context_hash", "decision", "credential_id", "invariant_results", "signature"})


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def rpc_error(request_id: Any, code: str, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class VerificationRuntime:
    def __init__(self, public_key: bytes) -> None:
        self.public_key = Ed25519PublicKey.from_public_bytes(public_key)
        self.lock = asyncio.Lock()
        self.version = 0
        self.state: dict[str, Any] = {"value": 0}

    def verify_receipt(self, receipt: Any) -> tuple[bool, str]:
        if not isinstance(receipt, dict) or not RECEIPT_FIELDS.issubset(receipt):
            return False, "receipt is missing required fields"
        if receipt.get("decision") != "ADMITTED":
            return False, "receipt decision is not ADMITTED"
        if (
            not isinstance(receipt["invariant_results"], dict)
            or not receipt["invariant_results"]
            or not all(receipt["invariant_results"].values())
        ):
            return False, "receipt invariants are not all true"
        signature = receipt.get("signature")
        if not isinstance(signature, str):
            return False, "receipt signature is malformed"
        signed = dict(receipt)
        signed.pop("signature")
        try:
            self.public_key.verify(bytes.fromhex(signature), canonical(signed))
        except (InvalidSignature, ValueError):
            return False, "receipt signature is invalid"
        return True, ""

    async def dispatch(self, method: str, params: Any) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
        if not isinstance(params, dict):
            return None, ("ERR_INVALID_PARAMS", "params must be an object")
        if method == "sdf.verify_receipt":
            valid, reason = self.verify_receipt(params.get("receipt"))
            return {"valid": valid, "reason": reason or None}, None
        if method == "benchmark.execute":
            spec = params.get("spec")
            if not isinstance(spec, dict) or not isinstance(spec.get("name"), str):
                return None, ("ERR_INVALID_BENCHMARK", "benchmark requires a name")
            valid, reason = self.verify_receipt(spec.get("receipt"))
            if not valid:
                return None, ("ERR_ATTESTATION", reason)
            return {"passed": True, "benchmark": spec["name"]}, None
        if method == "tx.submit_raw":
            payload = params.get("payload")
            valid, reason = self.verify_receipt(payload.get("receipt") if isinstance(payload, dict) else None)
            if not valid:
                return None, ("ERR_ATTESTATION", reason)
            return {"status": "ACCEPTED"}, None
        if method == "tx.commit":
            tx = params.get("tx")
            if not isinstance(tx, dict):
                return None, ("ERR_INVALID_TRANSACTION", "transaction must be an object")
            valid, reason = self.verify_receipt(tx.get("receipt"))
            if not valid:
                return None, ("ERR_ATTESTATION", reason)
            if not isinstance(tx.get("read_version"), int):
                return None, ("ERR_INVALID_TRANSACTION", "transaction requires integer read_version")
            async with self.lock:
                if tx["read_version"] != self.version:
                    return None, ("ERR_OCC_STALE_READ", "transaction read version is stale")
                self.version += 1
                self.state["value"] += 1
                return {"committed": True, "version": self.version}, None
        return None, ("ERR_METHOD_NOT_FOUND", "method is not supported")


async def serve(socket_path: Path, public_key: bytes) -> None:
    runtime = VerificationRuntime(public_key)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)

    async def client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.readline()
            if not raw or len(raw) > MAX_MESSAGE:
                return
            try:
                request = json.loads(raw)
                if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                response = rpc_error(None, "ERR_INVALID_REQUEST", "invalid JSON-RPC request")
            else:
                result, error = await runtime.dispatch(request["method"], request.get("params"))
                response = rpc_error(request.get("id"), *error) if error else {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
            writer.write(canonical(response) + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_unix_server(client, path=str(socket_path), limit=MAX_MESSAGE + 1)
    try:
        async with server:
            await server.serve_forever()
    finally:
        socket_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket-path", required=True)
    parser.add_argument("--public-key-file", default=os.environ.get("TAS_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--ephemeral", action="store_true")
    parser.add_argument("--storage-dir")
    args = parser.parse_args()
    if not args.public_key_file:
        parser.error("--public-key-file (or TAS_VERIFIER_PUBLIC_KEY) is required")
    if args.storage_dir:
        Path(args.storage_dir).mkdir(parents=True, exist_ok=True)
    key = bytes.fromhex(Path(args.public_key_file).read_text(encoding="ascii").strip())
    asyncio.run(serve(Path(args.socket_path), key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
