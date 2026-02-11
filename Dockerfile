# ──────────── Stage 1: Build frontend ────────────
FROM node:22-alpine AS frontend

WORKDIR /build
COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm install --prefer-offline --no-audit --no-fund
COPY app/frontend/ ./
RUN npm run build          # → /build/dist/

# ──────────── Stage 2: Python runtime ────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install Python deps
COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app/backend/ ./backend/

# Copy built frontend into static dir served by FastAPI
COPY --from=frontend /build/dist/ ./static/

# Cloud Run injects $PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
