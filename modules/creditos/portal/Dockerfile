FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Ruta donde se publica el portal: /portal-creditos/ (dev, dentro de Portezuelo) o / (su propio dominio).
ARG PORTAL_BASE=/portal-creditos/
ENV PORTAL_BASE=${PORTAL_BASE}
RUN npm run build

# ──────────────────────────────────────────
# Producción: nginx sirve el portal bajo /portal-creditos/ y los videos obligatorios del paso 4 desde
# /videos (carpeta del host montada; los archivos no van en la imagen ni en el repo).
# ──────────────────────────────────────────
FROM nginx:alpine AS production

ARG PORTAL_BASE=/portal-creditos/
COPY --from=builder /app/dist /usr/share/nginx/html${PORTAL_BASE}

# Con base "/" el portal está en la raíz; las rutas viejas /portal-creditos/... vuelven a la raíz.
RUN B="${PORTAL_BASE%/}"; \
    { echo "server {"; \
      echo "  listen 3000;"; \
      echo "  root /usr/share/nginx/html;"; \
      if [ -n "$B" ]; then echo "  location = $B { return 301 $B/; }"; \
      else echo "  location /portal-creditos/ { rewrite ^/portal-creditos/(.*)\$ /\$1 permanent; }"; fi; \
      echo "  location $B/videos/ { alias /videos/; types { video/mp4 mp4; } add_header Cache-Control \"public, max-age=86400\"; }"; \
      echo "  location $B/ { try_files \$uri \$uri/ $B/index.html; }"; \
      echo "}"; } > /etc/nginx/conf.d/default.conf && cat /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
