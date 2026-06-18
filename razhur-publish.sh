#!/usr/bin/env bash
#
# razhur-publish.sh — local publisher for the Razhur Content Bridge plugin.
#
# Sends a locally generated article (JSON payload) to a live WordPress site as a
# draft, embedding a featured image as base64. Push-only over HTTPS; no DB sync.
#
# Usage:
#   ./razhur-publish.sh payload.json [image-path]   # publish an article
#   ./razhur-publish.sh --status                    # test connectivity & auth
#
# Config is read from .razhur-bridge.env in the same directory:
#   RAZHUR_BRIDGE_URL, RAZHUR_BRIDGE_USER, RAZHUR_BRIDGE_APP_PASSWORD, RAZHUR_BRIDGE_TOKEN
#
# Requires: bash, curl, base64. Image injection additionally uses python3 (for
# safe JSON editing); if python3 is absent, embed the base64 yourself in the JSON.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.razhur-bridge.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Create it from the plugin's Help tab." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

: "${RAZHUR_BRIDGE_URL:?Set RAZHUR_BRIDGE_URL in .razhur-bridge.env}"
: "${RAZHUR_BRIDGE_USER:?Set RAZHUR_BRIDGE_USER in .razhur-bridge.env}"
: "${RAZHUR_BRIDGE_APP_PASSWORD:?Set RAZHUR_BRIDGE_APP_PASSWORD in .razhur-bridge.env}"
RAZHUR_BRIDGE_TOKEN="${RAZHUR_BRIDGE_TOKEN:-}"

BASE="${RAZHUR_BRIDGE_URL%/}/wp-json/razhur-content-bridge/v1"

# Build common curl auth args.
auth_args=(-u "${RAZHUR_BRIDGE_USER}:${RAZHUR_BRIDGE_APP_PASSWORD}")
if [[ -n "${RAZHUR_BRIDGE_TOKEN}" ]]; then
  auth_args+=(-H "X-Razhur-Bridge-Token: ${RAZHUR_BRIDGE_TOKEN}")
fi

# --status: just hit the status endpoint.
if [[ "${1:-}" == "--status" ]]; then
  curl -sS "${auth_args[@]}" "${BASE}/status"
  echo
  exit 0
fi

PAYLOAD="${1:?Usage: razhur-publish.sh payload.json [image-path]}"
IMAGE="${2:-}"

if [[ ! -f "${PAYLOAD}" ]]; then
  echo "ERROR: payload file not found: ${PAYLOAD}" >&2
  exit 1
fi

BODY_FILE="${PAYLOAD}"

# If an image path is given, inject its base64 into featured_image.data.
if [[ -n "${IMAGE}" ]]; then
  if [[ ! -f "${IMAGE}" ]]; then
    echo "ERROR: image file not found: ${IMAGE}" >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required to inject the image. Embed base64 manually instead." >&2
    exit 1
  fi
  B64="$(base64 < "${IMAGE}" | tr -d '\n')"
  TMP="$(mktemp)"
  PAYLOAD="${PAYLOAD}" B64="${B64}" python3 - "${TMP}" <<'PY'
import json, os, sys
out = sys.argv[1]
with open(os.environ["PAYLOAD"], encoding="utf-8") as fh:
    data = json.load(fh)
fi = data.setdefault("featured_image", {})
fi["data"] = os.environ["B64"]
with open(out, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)
PY
  BODY_FILE="${TMP}"
fi

# Send the request.
RESPONSE="$(curl -sS "${auth_args[@]}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  "${BASE}/publish")"

# Clean up any temp file.
[[ -n "${IMAGE}" ]] && rm -f "${BODY_FILE}"

echo "${RESPONSE}"

# Surface the edit link if jq or python3 is available; otherwise raw JSON is enough.
if command -v python3 >/dev/null 2>&1; then
  echo "${RESPONSE}" | python3 -c 'import json,sys
try:
    r=json.load(sys.stdin)
    if r.get("success"):
        print("\nDraft created. Review at:", r.get("edit_link",""))
        if r.get("image_error"): print("Image warning:", r["image_error"])
    else:
        print("\nFailed:", r.get("message", r))
except Exception:
    pass'
fi
