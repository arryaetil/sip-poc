FROM node:22-bookworm-slim
RUN npm install -g opencode-ai@1.18.34 && groupadd -g 10001 developer && useradd -u 10001 -g developer -m developer
COPY gateway.mjs /opt/developer/gateway.mjs
COPY entrypoint.sh /opt/developer/entrypoint.sh
RUN chmod 755 /opt/developer/entrypoint.sh
WORKDIR /data/projects
ENTRYPOINT ["/opt/developer/entrypoint.sh"]
