FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94
COPY docker/node-tools/package.json docker/node-tools/package-lock.json /opt/test-tools/
RUN cd /opt/test-tools && npm ci --ignore-scripts --no-audit --no-fund && rm -rf /root/.npm
COPY docker/node-compat/array-flatten/ /opt/test-tools/node_modules/array-flatten/
COPY docker/node-compat/manifest.json docker/node-compat/verify.cjs /opt/node-compat/
RUN node /opt/node-compat/verify.cjs && chmod -R a-w /opt/node-compat /opt/test-tools
WORKDIR /source
USER 1000:1000
