FROM node:22-alpine AS builder
WORKDIR /app

# 빌드 시점의 ARG 선언
ARG NEXT_PUBLIC_API_URL

# 빌드 환경에서 사용할 ENV 설정
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 의존성 설치
COPY package*.json ./
RUN npm ci

# 소스 코드 복사 및 빌드
COPY . .
RUN npm run build

# 2. Runner Stage: standalone 산출물로 실제 앱 실행
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup -S app && adduser -S -D -H -u 1001 app -G app

COPY --from=builder --chown=1001:1001 /app/public ./public
COPY --from=builder --chown=1001:1001 /app/.next/standalone ./
COPY --from=builder --chown=1001:1001 /app/.next/static ./.next/static

USER 1001:1001

EXPOSE 3000
CMD ["node", "server.js"]
