FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# ──────────────────────────────────────────
# Producción: nginx sirve el portal bajo /portal-creditos/
# ──────────────────────────────────────────
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html/portal-creditos

RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    location = /portal-creditos { return 301 /portal-creditos/; } \
    location /portal-creditos/ { \
        try_files $uri $uri/ /portal-creditos/index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
