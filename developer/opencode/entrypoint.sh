#!/bin/sh
set -eu
for name in DEVELOPER_HANDOFF_SECRET DEVELOPER_PUBLIC_URL OPENCODE_SERVER_PASSWORD; do
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then echo "$name is not set" >&2; exit 1; fi
done
mkdir -p /data/projects /data/home /data/used-links
chown -R developer:developer /data
cd /data/projects
runuser -u developer -- env HOME=/data/home XDG_DATA_HOME=/data/home/.local/share XDG_CONFIG_HOME=/data/home/.config XDG_STATE_HOME=/data/home/.local/state opencode web --hostname 127.0.0.1 --port 4096 &
exec runuser -u developer -- env HOME=/data/home XDG_DATA_HOME=/data/home/.local/share XDG_CONFIG_HOME=/data/home/.config XDG_STATE_HOME=/data/home/.local/state node /opt/developer/gateway.mjs
