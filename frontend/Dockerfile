# Build the SPA, then serve it with nginx. nginx also proxies the API (see nginx/default.conf.template).
# Images by digest: a tag can be moved to other contents, a digest can't. Dependabot bumps both.

FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS build
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: no install-time code from npm packages runs during the build.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN npm run build

# Runs as uid 101 and listens on 8080: no root in the running container.
FROM nginxinc/nginx-unprivileged:1.30-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
# Alpine ships fixes more often than this base is rebuilt: take them at build time.
USER 0
RUN apk upgrade --no-cache
USER 101
# nginx-conf is a named build context: ./nginx (see compose.yaml); hadolint takes it for a stage (DL3022).
# The entrypoint renders the template into /etc/nginx/conf.d at start; compose mounts a tmpfs there, as
# the root FS is read-only.
# hadolint ignore=DL3022
COPY --from=nginx-conf default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
# API docs (/docs): Swagger UI from the locked npm package and our page; no CDN at runtime.
COPY --from=build /app/node_modules/swagger-ui-dist/swagger-ui-bundle.js \
    /app/node_modules/swagger-ui-dist/swagger-ui.css /usr/share/nginx/html/swagger/
# hadolint ignore=DL3022
COPY --from=nginx-conf swagger/ /usr/share/nginx/html/swagger/
