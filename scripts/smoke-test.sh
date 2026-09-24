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
