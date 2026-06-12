# Stage 1: build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: production Python image
FROM python:3.12-slim AS app
WORKDIR /app

# System deps for Playwright + Crawl4AI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libfontconfig1 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic (lightweight LaTeX engine)
RUN curl -L "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz" \
    | tar xz -C /usr/local/bin \
    && tectonic --version

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy application code
COPY backend/ ./backend/
COPY presets/ ./presets/
COPY alembic.ini ./

# Copy built frontend into the static directory FastAPI serves
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Run Alembic migrations then start Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
