#!/usr/bin/env python3
"""Run the shared arithmetic vectors; this is not a protocol verifier.

Only settlement arithmetic and the ledger UInt64 conversion guard are covered.
Unknown families and malformed vectors are errors, never skipped.
"""

import json
import sys
from pathlib import Path

from tas_conformance_harness import SettlementSlice, calculate_batch_allocations


LIMIT = 1 << 64
LEDGER_FIELDS = ("r_gross", "r_legal", "r_infra", "r_dist", "liquid_sum",
                 "escrow_sum", "escrow_bal")


def object_fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"expected exactly fields {', '.join(fields)}")
    return value


def natural(value):
    if type(value) is not int or value < 0:
        raise ValueError("expected nonnegative integer")
    return value


def identifier(value):
    if not isinstance(value, str) or not value or not value.isascii():
        raise ValueError("expected nonempty ASCII identifier")
    return value


def payment(value):
    object_fields(value, ("artifact_id", "amount"))
    return {"artifact_id": identifier(value["artifact_id"]),
            "amount": natural(value["amount"])}


def settlement(vector):
    object_fields(vector, ("id", "pool", "shares", "expected"))
    identifier(vector["id"])
    pool = natural(vector["pool"])
    if pool >= LIMIT or not isinstance(vector["shares"], list) or not vector["shares"]:
        raise ValueError("invalid pool or shares")
    shares = []
    seen = set()
    for share in vector["shares"]:
        object_fields(share, ("artifact_id", "bps", "contested"))
        name, bps = identifier(share["artifact_id"]), natural(share["bps"])
        if name in seen or bps > 10000 or type(share["contested"]) is not bool:
            raise ValueError("invalid or duplicate share")
        seen.add(name)
        shares.append(share)
    if sum(s["bps"] for s in shares) != 10000:
        raise ValueError("basis points must sum to 10000")
    if any(pool * s["bps"] >= LIMIT for s in shares):
        raise ValueError("settlement intermediate exceeds UInt64")
    expected = object_fields(vector["expected"], ("settled", "escrow", "legal_reserve"))
    if not isinstance(expected["settled"], list) or not isinstance(expected["escrow"], list):
        raise ValueError("expected payments must be arrays")
    expected = {"settled": [payment(p) for p in expected["settled"]],
                "escrow": [payment(p) for p in expected["escrow"]],
                "legal_reserve": natural(expected["legal_reserve"])}
    slices = [SettlementSlice(s["artifact_id"], s["bps"]) for s in shares]
    amounts = calculate_batch_allocations(pool, slices)
    order = sorted(range(len(shares)),
                   key=lambda i: (-(pool * shares[i]["bps"] % 10000),
                                  shares[i]["artifact_id"]))
    actual = {"settled": [], "escrow": [], "legal_reserve": 0}
    for i in order:
        key = "escrow" if shares[i]["contested"] else "settled"
        actual[key].insert(0, {"artifact_id": amounts[i].artifact_id,
                               "amount": amounts[i].amount})
    if actual != expected:
        raise ValueError(f"settlement {vector['id']}: expected {expected}, got {actual}")


def uint64_ledger(vector):
    object_fields(vector, ("id", "ledger", "expected"))
    identifier(vector["id"])
    ledger = object_fields(vector["ledger"], LEDGER_FIELDS)
    for value in ledger.values():
        natural(value)
    if type(vector["expected"]) is not bool:
        raise ValueError("expected must be boolean")
    actual = ledger["r_gross"] * 1500 < LIMIT and all(v < LIMIT for v in ledger.values())
    if actual != vector["expected"]:
        raise ValueError(f"uint64_ledger {vector['id']}: expected {vector['expected']}, got {actual}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    if len(sys.argv) > 2:
        raise ValueError("usage: run_vectors.py [path]")
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("tas_vectors_v0_7_0.json")
    with path.open(encoding="utf-8") as source:
        data = json.load(source, object_pairs_hook=unique_object,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    object_fields(data, ("version", "families"))
    if data["version"] != "0.7.0" or not isinstance(data["families"], dict) or not data["families"]:
        raise ValueError("invalid version or empty families")
    runners = {"settlement": settlement, "uint64_ledger": uint64_ledger}
    counts = []
    for family, vectors in data["families"].items():
        if family not in runners:
            raise ValueError(f"unsupported family: {family}")
        if not isinstance(vectors, list) or not vectors:
            raise ValueError(f"empty or invalid family: {family}")
        ids = set()
        for vector in vectors:
            runners[family](vector)
            if vector["id"] in ids:
                raise ValueError(f"duplicate vector id in {family}: {vector['id']}")
            ids.add(vector["id"])
        counts.append(f"{family}={len(vectors)}")
    print("PASS arithmetic only: " + ", ".join(counts))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
