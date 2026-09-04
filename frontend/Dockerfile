# W2Health Intelligence — frontend (Next.js 14, App Router)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
# NEXT_PUBLIC_* precisa existir em tempo de build (o Next inlina no bundle).
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# ^ o Docker injeta HOSTNAME=<container id> e o server standalone do Next passa a
#   escutar só nesse IP. Fixar 0.0.0.0 para escutar em todas as interfaces (inclui loopback).
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
