#!/usr/bin/env bash
set -euo pipefail

# Finalize an uploaded Harmonika HAI release on the production server.
#
# This script is intentionally server-side and secret-free. Upload the archive to
# /tmp/<release>.tar.gz first, then run:
#
#   HAI_RELEASE_NAME=harmonika-chat-webui-release-... \
#   bash scripts/hai_finalize_remote_release.sh
#
# Why this exists:
# A release directory must reuse the existing production virtualenv. If the new
# release links `.venv` to `/srv/harmonika-chat-webui/.venv` and then the
# production symlink is switched to that new release, `.venv` can become a
# self-referential loop. systemd then fails with status 203/EXEC. This script
# resolves the current real venv before switching the production symlink.

RELEASE_NAME="${HAI_RELEASE_NAME:-${1:-}}"
APP_LINK="${HAI_APP_LINK:-/srv/harmonika-chat-webui}"
RELEASE_ROOT="${HAI_RELEASE_ROOT:-/srv}"
SERVICE_NAME="${HAI_SERVICE_NAME:-harmonika-hai-web.service}"
HEALTH_URL="${HAI_HEALTH_URL:-http://127.0.0.1:3002/healthz}"
ARCHIVE_PATH="${HAI_RELEASE_ARCHIVE:-}"

if [[ -z "$RELEASE_NAME" ]]; then
  echo "error: set HAI_RELEASE_NAME or pass release name as first argument" >&2
  exit 64
fi

if [[ "$RELEASE_NAME" == */* || "$RELEASE_NAME" == .* ]]; then
  echo "error: release name must be a plain directory name: $RELEASE_NAME" >&2
  exit 64
fi

if [[ -z "$ARCHIVE_PATH" ]]; then
  ARCHIVE_PATH="/tmp/${RELEASE_NAME}.tar.gz"
fi

RELEASE_DIR="${RELEASE_ROOT}/${RELEASE_NAME}"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "error: archive not found: $ARCHIVE_PATH" >&2
  exit 66
fi

resolve_current_venv() {
  local current=""
  if [[ -e "${APP_LINK}/.venv" ]]; then
    current="$(readlink -f "${APP_LINK}/.venv" || true)"
  fi
  if [[ -n "$current" && -x "${current}/bin/gunicorn" && "$current" != "${APP_LINK}/.venv" ]]; then
    printf '%s\n' "$current"
    return 0
  fi
  find "$RELEASE_ROOT" -maxdepth 3 -path '*/.venv/bin/gunicorn' -type f -perm -111 -print -quit \
    | sed 's#/bin/gunicorn$##'
}

REAL_VENV="$(resolve_current_venv)"
if [[ -z "$REAL_VENV" || ! -x "${REAL_VENV}/bin/gunicorn" ]]; then
  echo "error: could not resolve a usable production venv with gunicorn" >&2
  exit 69
fi

mkdir -p "$RELEASE_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$RELEASE_DIR"

rm -f "${RELEASE_DIR}/.venv"
ln -s "$REAL_VENV" "${RELEASE_DIR}/.venv"

RESOLVED_NEW_VENV="$(readlink -f "${RELEASE_DIR}/.venv" || true)"
if [[ "$RESOLVED_NEW_VENV" != "$REAL_VENV" || ! -x "${RELEASE_DIR}/.venv/bin/gunicorn" ]]; then
  echo "error: new release venv validation failed" >&2
  echo "expected: $REAL_VENV" >&2
  echo "actual:   ${RESOLVED_NEW_VENV:-<empty>}" >&2
  exit 69
fi

chown -R root:root "$RELEASE_DIR"
ln -sfn "$RELEASE_DIR" "$APP_LINK"

POST_SWITCH_VENV="$(readlink -f "${APP_LINK}/.venv" || true)"
if [[ "$POST_SWITCH_VENV" != "$REAL_VENV" || ! -x "${APP_LINK}/.venv/bin/gunicorn" ]]; then
  echo "error: production venv validation failed after symlink switch" >&2
  echo "expected: $REAL_VENV" >&2
  echo "actual:   ${POST_SWITCH_VENV:-<empty>}" >&2
  exit 69
fi

systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"

health_ok=0
for attempt in $(seq 1 20); do
  if curl -fsS "$HEALTH_URL" >/dev/null; then
    health_ok=1
    break
  fi
  sleep 0.5
done

if [[ "$health_ok" != "1" ]]; then
  echo "error: health check did not become ready: $HEALTH_URL" >&2
  systemctl status "$SERVICE_NAME" --no-pager -l >&2 || true
  exit 70
fi

echo "ok: release finalized"
echo "release=${RELEASE_DIR}"
echo "venv=${REAL_VENV}"
echo "service=${SERVICE_NAME}"
