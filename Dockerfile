FROM node:18-alpine AS builder
WORKDIR /app

# 빌드 시점의 ARG 선언
ARG NEXT_PUBLIC_API_URL

# 빌드 환경에서 사용할 ENV 설정
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 의존성 설치
COPY package*.json ./
RUN npm install

# 소스 코드 복사 및 빌드
COPY . .
RUN npm run build

# 2. Runner Stage: 빌드된 결과물로 실제 앱 실행
FROM node:18-alpine AS runner
WORKDIR /app

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 빌드 단계에서 생성된 파일들을 복사
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]