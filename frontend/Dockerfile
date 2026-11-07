# Build the SPA, then serve it with nginx. nginx also proxies the API (see nginx/default.conf.template).

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: no install-time code from npm packages runs during the build.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN npm run build

# Runs as uid 101 and listens on 8080: no root in the running container.
FROM nginxinc/nginx-unprivileged:1.30-alpine
# nginx-conf is a named build context: ./nginx (see compose.yaml). The entrypoint renders the template
# into /etc/nginx/conf.d at start; compose mounts a tmpfs there, as the root FS is read-only.
COPY --from=nginx-conf default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
