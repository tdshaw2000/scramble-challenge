#!/bin/sh
# Smoke test for the Docker Compose stack (Dockerfiles and Compose can't be unit tested).
# Run after `docker compose up -d`: checks the app is healthy and can get a scramble
# and its SVG from TNoodle over the Compose network.
set -e

PORT="${WEB_PORT:-5000}"

echo "Waiting for web /healthz on port $PORT..."
i=0
until curl -sf "http://localhost:$PORT/healthz" > /dev/null; do
  i=$((i + 1))
  [ "$i" -ge 30 ] && { echo "FAIL: /healthz never came up"; exit 1; }
  sleep 2
done
echo "ok: /healthz"

echo "Waiting for TNoodle (reached from the web container)..."
i=0
until docker compose exec -T web python - <<'PY'
import json, urllib.parse, urllib.request
base = "http://tnoodle:2014/api/v0"
scramble = json.loads(urllib.request.urlopen(f"{base}/scramble/333").read())[0]
query = urllib.parse.urlencode({"scramble": scramble})
svg = urllib.request.urlopen(f"{base}/view/333/svg?{query}").read().decode()
assert svg.startswith("<svg"), svg[:80]
print(f"ok: scramble {scramble!r} and SVG ({len(svg)} bytes)")
PY
do
  i=$((i + 1))
  [ "$i" -ge 30 ] && { echo "FAIL: TNoodle never answered"; exit 1; }
  sleep 2
done

# Through Caddy, the way players come in. On the server SITE_ADDRESS is the public
# domain (HTTPS, checked against this machine); in CI and locally it's plain ":80".
SITE="${SITE_ADDRESS:-:80}"
if [ "${SITE#:}" != "$SITE" ]; then
  BASE="http://localhost$SITE"
  set --
else
  BASE="https://$SITE"
  set -- --resolve "$SITE:443:127.0.0.1"
fi

echo "Waiting for $BASE/healthz through Caddy..."
i=0
until curl -sf "$@" "$BASE/healthz" > /dev/null; do
  i=$((i + 1))
  # The first HTTPS start includes getting a certificate, so allow a couple of minutes.
  [ "$i" -ge 60 ] && { echo "FAIL: $BASE/healthz never came up through Caddy"; exit 1; }
  sleep 2
done
echo "ok: $BASE/healthz through Caddy"

echo "Checking a WebSocket upgrade through Caddy..."
# The connection stays open after the upgrade, so curl times out; only the status matters.
response=$(curl -si --http1.1 --max-time 5 "$@" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: c21va2UtdGVzdC1rZXkhIQ==" \
  "$BASE/socket.io/?EIO=4&transport=websocket" || true)
if ! echo "$response" | head -1 | grep -q " 101"; then
  echo "FAIL: expected 101 Switching Protocols, got:"
  echo "$response" | head -5
  exit 1
fi
echo "ok: WebSocket upgrade through Caddy"
