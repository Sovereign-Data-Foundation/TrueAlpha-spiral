#!/usr/bin/env bash
set -Eeuo pipefail
: "${VERIFY_ROOT:=/opt/tas/verification}" "${ADAPTER_BIN:=/opt/tas/bin/runtime_adapter}"
: "${ADAPTER_SOCKET:=/run/prod_runtime.sock}" "${TEST_LOG_DIR:?TEST_LOG_DIR is required}"
shopt -s nullglob
receipts=("${VERIFY_ROOT}/fixtures/receipts"/*.json)
[[ ${#receipts[@]} -eq 6 ]] || { echo "[FATAL] Expected exactly 6 receipt fixtures, found ${#receipts[@]}" >&2; exit 1; }
: >"${TEST_LOG_DIR}/receipt_checks.log"
for receipt in "${receipts[@]}"; do
    "${ADAPTER_BIN}" client verify-receipt --socket="${ADAPTER_SOCKET}" --input="${receipt}" \
        >>"${TEST_LOG_DIR}/receipt_checks.log" 2>&1
done
echo "[PHASE 1] Success: 6/6 receipt checks passed."
