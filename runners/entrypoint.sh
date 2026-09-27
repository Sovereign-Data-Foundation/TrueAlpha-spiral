#!/usr/bin/env bash
set -Eeuo pipefail

RUNNERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VERIFY_ROOT="${VERIFY_ROOT:-/opt/tas/verification}"
export WORKDIR="${WORKDIR:-${VERIFY_ROOT}/workdir}"
export ARTIFACT_OUT_DIR="${ARTIFACT_OUT_DIR:-/opt/tas/output}"
export ADAPTER_SOCKET="${ADAPTER_SOCKET:-/run/prod_runtime.sock}"
export PROD_RUNTIME_BIN="${PROD_RUNTIME_BIN:-/opt/tas/bin/prod_runtime}"
export ADAPTER_BIN="${ADAPTER_BIN:-/opt/tas/bin/runtime_adapter}"
export TEST_LOG_DIR="${TEST_LOG_DIR:-${WORKDIR}/logs}"

mkdir -p "${WORKDIR}" "${ARTIFACT_OUT_DIR}" "${TEST_LOG_DIR}"
RUNTIME_PID=""

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ -n "${RUNTIME_PID}" ]] && kill -0 "${RUNTIME_PID}" 2>/dev/null; then
        kill -TERM "${RUNTIME_PID}" 2>/dev/null || true
        for _ in {1..50}; do
            kill -0 "${RUNTIME_PID}" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL "${RUNTIME_PID}" 2>/dev/null || true
        wait "${RUNTIME_PID}" 2>/dev/null || true
    fi
    rm -f "${ADAPTER_SOCKET}"
    if (( exit_code != 0 )); then
        echo "[SUPERVISOR] Execution failed with exit code ${exit_code}." >&2
    fi
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM

echo "[SUPERVISOR] Starting isolated production-runtime verification suite"
"${RUNNERS_DIR}/00_verify_fixtures.sh"

[[ -x "${PROD_RUNTIME_BIN}" ]] || { echo "[FATAL] Runtime is not executable: ${PROD_RUNTIME_BIN}" >&2; exit 1; }
[[ -x "${ADAPTER_BIN}" ]] || { echo "[FATAL] Adapter is not executable: ${ADAPTER_BIN}" >&2; exit 1; }
rm -f "${ADAPTER_SOCKET}"
"${PROD_RUNTIME_BIN}" --socket-path="${ADAPTER_SOCKET}" --ephemeral \
    --storage-dir="${WORKDIR}/runtime_store" >"${TEST_LOG_DIR}/runtime.log" 2>&1 &
RUNTIME_PID=$!

for _ in {1..100}; do
    [[ -S "${ADAPTER_SOCKET}" ]] && break
    kill -0 "${RUNTIME_PID}" 2>/dev/null || { cat "${TEST_LOG_DIR}/runtime.log" >&2; exit 1; }
    sleep 0.1
done
[[ -S "${ADAPTER_SOCKET}" ]] || { echo "[FATAL] Runtime socket readiness timed out" >&2; exit 1; }

"${RUNNERS_DIR}/01_run_receipt_checks.sh"
"${RUNNERS_DIR}/02_run_benchmarks.sh"
"${RUNNERS_DIR}/03_run_fault_tests.sh"
"${RUNNERS_DIR}/04_generate_receipt.sh"
echo "[SUPERVISOR] Verification completed successfully."
