# Stage 1: build the Vue SPA
FROM node:22-slim AS ui-build
WORKDIR /build
COPY src/ui/package*.json ./
RUN npm ci
COPY src/ui/ ./
RUN npm run build

# Stage 2: Python daemon
FROM python:3.12-slim

# Install gosu for PUID/PGID support
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy static ffmpeg/ffprobe binaries (avoids apt network issues)
COPY --from=mwader/static-ffmpeg:latest /ffmpeg /usr/local/bin/ffmpeg
COPY --from=mwader/static-ffmpeg:latest /ffprobe /usr/local/bin/ffprobe

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .

# Copy built UI into the location FastAPI serves from
COPY --from=ui-build /build/dist /app/src/ui/dist

# .data volume: persistent DB storage
# downloads volume: downloaded media
VOLUME ["/app/.data", "/app/downloads"]

EXPOSE 8000

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["siphon", "watch"]
