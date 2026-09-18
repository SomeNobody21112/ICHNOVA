# ICHNOVA — working deployment: the real engine, not a replay.
#
# Stage 1 builds the console; stage 2 runs the analysis server (numpy + scipy only) and serves the
# built console from the same process. A capture uploaded to the running container is analysed by the
# same code as `python server/app.py` locally, so a deployed instance is a working model, not a
# playback of stored results.
#
# Build and run locally:
#   docker build -t ichnova . && docker run --rm -p 7860:7860 ichnova
# Hugging Face Spaces (SDK: docker) listens on 7860; PORT overrides it.

FROM node:22-slim AS console
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
RUN cd frontend && npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=7860
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Engine, server, reference constants and the committed real recordings (the console replays them).
COPY src ./src
COPY server ./server
COPY references ./references
COPY recordings ./recordings
COPY --from=console /build/frontend/dist ./frontend/dist

# Non-root, writable results directory for live sessions.
RUN useradd --create-home --uid 1000 ichnova && mkdir -p /app/results && chown -R ichnova /app
USER ichnova

EXPOSE 7860
CMD ["python", "server/app.py"]
