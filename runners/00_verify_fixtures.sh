#!/usr/bin/env bash
set -Eeuo pipefail
: "${VERIFY_ROOT:=/opt/tas/verification}"
CHECKSUM_FILE="${FIXTURE_CHECKSUM_FILE:-${VERIFY_ROOT}/fixtures.sha256}"
[[ -f "${CHECKSUM_FILE}" ]] || { echo "[FATAL] Missing checksum manifest: ${CHECKSUM_FILE}" >&2; exit 1; }
echo "[PHASE 0] Verifying pinned fixtures..."
(cd "${VERIFY_ROOT}" && sha256sum --strict -c "${CHECKSUM_FILE}")
