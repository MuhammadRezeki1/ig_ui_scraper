# ============ Stage 1: Install dependencies ============
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# ============ Stage 2: Build Next.js ============
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* harus tersedia saat BUILD — Next.js meng-inline-nya ke bundle
# browser. Set lewat build arg (lihat docker-compose.yml → build.args).
# Default localhost:8000 cocok untuk jalan lokal; untuk server isi dengan
# URL publik backend (mis. https://api.domainmu.com).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build Next.js (hasil: .next/standalone)
RUN npm run build

# ============ Stage 3: Production runner ============
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Bikin non-root user untuk security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy hasil build standalone (super minimal)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]