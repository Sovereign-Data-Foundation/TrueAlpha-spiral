#!/usr/bin/env bash
set -Eeuo pipefail
: "${VERIFY_ROOT:=/opt/tas/verification}" "${ADAPTER_BIN:=/opt/tas/bin/runtime_adapter}"
: "${ADAPTER_SOCKET:=/run/prod_runtime.sock}" "${TEST_LOG_DIR:?TEST_LOG_DIR is required}"
shopt -s nullglob
benchmarks=("${VERIFY_ROOT}/fixtures/benchmarks"/bench_*.json)
[[ ${#benchmarks[@]} -eq 15 ]] || { echo "[FATAL] Expected exactly 15 benchmarks, found ${#benchmarks[@]}" >&2; exit 1; }
: >"${TEST_LOG_DIR}/benchmarks.log"
for spec in "${benchmarks[@]}"; do
    "${ADAPTER_BIN}" client exec-benchmark --socket="${ADAPTER_SOCKET}" --spec="${spec}" \
        >>"${TEST_LOG_DIR}/benchmarks.log" 2>&1
done
race_result=$("${ADAPTER_BIN}" client run-race --socket="${ADAPTER_SOCKET}" \
    --competing-tx="${VERIFY_ROOT}/fixtures/races/tx_fresh.json" \
    --stale-tx="${VERIFY_ROOT}/fixtures/races/tx_stale.json")
printf '%s\n' "${race_result}" >>"${TEST_LOG_DIR}/benchmarks.log"
python -c 'import json,sys; r=json.load(sys.stdin); assert r == {"competing_committed": True, "conflict_code": "ERR_OCC_STALE_READ", "stale_rejected": True}' <<<"${race_result}"
echo "[PHASE 2] Success: 15 benchmarks and OCC race passed."
