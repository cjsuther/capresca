FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ──────────────────────────────────────────
# Producción: nginx sirve la SPA bajo /creditos/
# ──────────────────────────────────────────
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html/creditos

RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    location = /creditos { return 301 /creditos/; } \
    location /creditos/ { \
        try_files $uri $uri/ /creditos/index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
