# Production-runtime adapter contract (v0.1)

This is the boundary between the isolated verification runner and the actual
production runtime. A successful reference-suite result is not a qualification
result: only the runtime behind this contract may issue a `QUALIFIED` receipt.

## Transport and envelope

The adapter uses one request per Unix-domain-socket connection. Requests and
responses are UTF-8, newline-delimited JSON-RPC 2.0 objects, limited to 8 MiB.
The runtime must echo the request `id`; a malformed request is rejected with a
JSON-RPC error and never executed. The allowed methods are exactly:

| Method | Required input | Success result | Rejection |
| --- | --- | --- | --- |
| `sdf.verify_receipt` | `receipt` | `{valid: true}` | `{valid: false}` |
| `benchmark.execute` | named `spec` with `receipt` | `{passed: true}` | `ERR_ATTESTATION` |
| `tx.submit_raw` | payload with `receipt` | `{status: "ACCEPTED"}` | `ERR_ATTESTATION` |
| `tx.commit` | `read_version` and `receipt` | `{committed: true, version}` | `ERR_OCC_STALE_READ` or `ERR_ATTESTATION` |

A receipt contains `id`, `candidate_hash`, `context_hash`, `decision`,
`credential_id`, `invariant_results`, and a hexadecimal Ed25519 `signature`.
The signature covers the canonical JSON object with `signature` omitted. Canonical
JSON sorts object keys and uses compact separators. The trusted verifier key is
supplied only by `--public-key-file` (or `TAS_VERIFIER_PUBLIC_KEY`); keys in an
untrusted request are never accepted as trust roots.

## Fail-closed rules

* Missing, malformed, non-`ADMITTED`, invariant-failing, or invalidly signed
  receipts reject execution with `ERR_ATTESTATION`.
* No RPC bypass method, unsigned development mode, or acceptance fallback exists.
* Commit is serialized; a transaction whose `read_version` differs from the
  current version receives `ERR_OCC_STALE_READ` and changes no state.
* The runner must treat absent fixtures, checksum failures, unavailable runtime,
  transport errors, and unsigned qualification evidence as gate failures.

## Qualification evidence

The runner hashes its complete logs into `execution_digest`, signs the generated
receipt, and marks it `QUALIFIED` only after all fixture, receipt, benchmark,
race, and negative checks pass. An unsigned result is `PENDING`, not qualified.

## Isolated execution

Build the image from this repository, mount the independently pinned verification
bundle read-only, and supply the verifier public key plus a gate-signing private
key read-only. The container exposes no network service; the runtime and adapter
communicate only over its private Unix socket.

```sh
docker build -t tas-production-gate:local .
docker run --rm --network none \
  -v "$PWD/TAS_Verification_Benchmarks_v0.1:/opt/tas/verification:ro" \
  -v "$PWD/verifier_public_key.hex:/opt/tas/certs/verifier_public_key.hex:ro" \
  -v "$PWD/gate_signing_key.pem:/opt/tas/certs/gate_signing_key.pem:ro" \
  -v "$PWD/verification-output:/opt/tas/output" \
  tas-production-gate:local
```

The process exits nonzero for every gate failure. On success it writes both
`prod_verification_receipt.json` and its detached signature to the output mount.
