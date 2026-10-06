# W2Health Intelligence — frontend (Next.js 15, App Router, output standalone).
# Multi-stage: dependências e build ficam fora da imagem final; runtime roda como usuário
# não-root, sem node_modules de desenvolvimento, sem código-fonte e sem source maps públicos.
ARG NODE_IMAGE=node:20-alpine

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM ${NODE_IMAGE} AS builder
WORKDIR /app
# NEXT_PUBLIC_* é inlinado no bundle em tempo de build (não é segredo — é a URL pública da API).
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
# HSTS no próprio frontend só quando servido atrás de TLS (normalmente o proxy já envia).
ARG ENABLE_HSTS=false
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    ENABLE_HSTS=$ENABLE_HSTS
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# ^ o Docker injeta HOSTNAME=<container id> e o server standalone do Next passa a
#   escutar só nesse IP. Fixar 0.0.0.0 para escutar em todas as interfaces (inclui loopback).
RUN addgroup -S -g 10001 w2h && adduser -S -u 10001 -G w2h -H w2h
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.js"]
