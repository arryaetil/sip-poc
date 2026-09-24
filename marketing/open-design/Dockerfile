# Open Design for the SIP marketing studio spike, with the Etil and ibc group
# design systems preinstalled.
#
# Pinned by digest: the published image that was "latest" on 24-09-2026
# (release open-design-v0.24.0, 22-09-2026). Change deliberately, never float.
FROM ghcr.io/nexu-io/od@sha256:01f4157acb4b6b115911135aa65d9f78f14d51f7a3e5010eb18ac8cebdf1286b

USER root
COPY design-systems /seed/design-systems
COPY entrypoint.sh /seed/entrypoint.sh
COPY gateway.mjs /seed/gateway.mjs
COPY configure-studio.mjs /seed/configure-studio.mjs
RUN chmod +x /seed/entrypoint.sh

# The BYOK runtime ("OpenAI API via OpenCode") runs the OpenCode CLI, which the
# upstream image deliberately does not bundle. Pinned; the musl build is picked
# automatically on Alpine.
RUN npm install -g opencode-ai@1.18.32 && opencode --version

# The entrypoint runs as root only long enough to prepare the mounted volume,
# then starts the daemon (localhost only) and the SIP gateway as the image's
# unprivileged open-design user.
ENTRYPOINT ["/sbin/tini", "--", "/seed/entrypoint.sh"]
