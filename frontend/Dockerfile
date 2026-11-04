# Build the SPA, then serve it with nginx. nginx also proxies the API (see nginx/default.conf).

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.30-alpine
# nginx-conf is a named build context: ./nginx (see compose.yaml).
COPY --from=nginx-conf default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
