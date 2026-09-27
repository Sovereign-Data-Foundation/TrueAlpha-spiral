#!/usr/bin/env bash
set -Eeuo pipefail
: "${VERIFY_ROOT:=/opt/tas/verification}" "${ADAPTER_BIN:=/opt/tas/bin/runtime_adapter}"
: "${ADAPTER_SOCKET:=/run/prod_runtime.sock}" "${TEST_LOG_DIR:?TEST_LOG_DIR is required}"
shopt -s nullglob
specimens=("${VERIFY_ROOT}/fixtures/broken_specimens"/broken_*.json)
[[ ${#specimens[@]} -eq 5 ]] || { echo "[FATAL] Expected exactly 5 broken specimens, found ${#specimens[@]}" >&2; exit 1; }
: >"${TEST_LOG_DIR}/fault_tests.log"
for specimen in "${specimens[@]}"; do
    output=$("${ADAPTER_BIN}" client submit --socket="${ADAPTER_SOCKET}" --payload="${specimen}" \
        2>>"${TEST_LOG_DIR}/fault_tests.log") || {
        echo "[FATAL] Adapter/transport failure for ${specimen}" >&2
        exit 1
    }
    printf '%s\n' "${output}" >>"${TEST_LOG_DIR}/fault_tests.log"
    python -c 'import json,sys; assert json.load(sys.stdin).get("status") == "REJECTED"' <<<"${output}" || {
        echo "[FATAL] Broken specimen was not explicitly rejected: ${specimen}" >&2
        exit 1
    }
done
echo "[PHASE 3] Success: 5/5 broken specimens rejected."
