FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir '.[hub]' && useradd --create-home --uid 10001 aek
COPY --from=frontend /frontend/dist /app/dashboard/dist
ENV AEK_STATIC_DIR=/app/dashboard/dist
USER aek
EXPOSE 8787
CMD ["aek-hub", "serve", "--host", "0.0.0.0", "--port", "8787"]
