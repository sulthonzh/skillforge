# SkillForge Web UI — standalone static export.
#
# In the recommended single-container setup, apps/api/Dockerfile builds this
# export itself and serves it from FastAPI. This Dockerfile exists for the
# optional two-service docker-compose profile where you want the Web UI served
# by its own container.

FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# NEXT_PUBLIC_API_URL is baked in at build time. Empty = same-origin (use this
# image behind a reverse proxy). For a separate-port setup, set it to the API URL.
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN npm install -g serve@14
COPY --from=builder /app/out ./out
EXPOSE 3000
CMD ["serve", "-s", "out", "-l", "3000"]
