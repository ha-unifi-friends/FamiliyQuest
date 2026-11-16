#!/usr/bin/with-contenv sh
# with-contenv: the s6-overlay of the Home Assistant base image only passes the container environment
# (SUPERVISOR_TOKEN for the Home Assistant API) to programs started like this.
set -e
mkdir -p /share/family_quest/packs
cd /app
exec python3 -m uvicorn familyquest.main:app_factory --factory --host 0.0.0.0 --port 8099 --no-proxy-headers --log-level warning
