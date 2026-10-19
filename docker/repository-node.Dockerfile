FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94
# Only trusted, locked test tools are installed at build time. No repository build context.
COPY docker/node-tools/package.json docker/node-tools/package-lock.json /opt/test-tools/
RUN cd /opt/test-tools && npm ci --ignore-scripts --no-audit --no-fund && rm -rf /root/.npm
WORKDIR /source
USER 1000:1000
