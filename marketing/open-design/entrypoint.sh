#!/bin/sh
# Prepare the data volume, install the brand design systems, start Open Design
# on localhost and the SIP gateway on Railway's port.
set -eu

DATA_DIR="${OD_DATA_DIR:-/app/.od}"
INTERNAL_PORT="${OD_INTERNAL_PORT:-7456}"

# Fail closed: the gateway admits nobody without these, the daemon is never public.
for name in OD_API_TOKEN STUDIO_HANDOFF_SECRET SIP_ORIGIN; do
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then
    echo "$name is not set; refusing to start." >&2
    exit 1
  fi
done

# Railway mounts volumes owned by root; the daemon runs as open-design (1001).
mkdir -p "$DATA_DIR/design-systems" "$DATA_DIR/home"
# Brand packages are overwritten on every start so a redeploy ships changes.
cp -R /seed/design-systems/. "$DATA_DIR/design-systems/"
chown -R 1001:1001 "$DATA_DIR"

# The daemon only listens on localhost; the gateway is the one way in.
# Image generation reads the OpenAI key from OD_OPENAI_API_KEY; the same key
# the gateway uses for text. Exported (not on the command line) so it stays
# out of the process list.
if [ -n "${STUDIO_OPENAI_API_KEY:-}" ]; then export OD_OPENAI_API_KEY="$STUDIO_OPENAI_API_KEY"; fi

# OpenCode keeps its config and auth under HOME; the image user has none.
su -s /bin/sh open-design -c "cd /app && HOME='$DATA_DIR/home' OD_DATA_DIR='$DATA_DIR' OD_PORT='$INTERNAL_PORT' OD_BIND_HOST=127.0.0.1 exec node apps/daemon/dist/cli.js --no-open" &

export OD_INTERNAL_PORT="$INTERNAL_PORT"
exec su -s /bin/sh open-design -c "exec node /seed/gateway.mjs"
