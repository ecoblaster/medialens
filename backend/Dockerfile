FROM node:22-alpine AS frontend-build
ARG MEDIALENS_BUILD_VERSION=1.1.0
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend ./
RUN sed -i "s/0.6.2-dev/${MEDIALENS_BUILD_VERSION}/g" src/App.tsx \
    && npm run build

FROM python:3.12-slim
ARG MEDIALENS_BUILD_VERSION=1.1.0
ARG DOVI_TOOL_VERSION=2.3.3
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MEDIALENS_APP_VERSION=${MEDIALENS_BUILD_VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl ffmpeg mediainfo \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    architecture="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$architecture" in \
      amd64|x86_64) \
        archive_arch="x86_64"; \
        archive_sha="5dae82cb2becd3b9fd726127f936a8d32635e60746d16238fdfded12aa05988c" \
        ;; \
      arm64|aarch64) \
        archive_arch="aarch64"; \
        archive_sha="daf538c275f4e702219ce8eb61db28382193ac9d0126e1ef4185a88303af4485" \
        ;; \
      *) echo "Unsupported dovi_tool architecture: $architecture" >&2; exit 1 ;; \
    esac; \
    archive="dovi_tool-${DOVI_TOOL_VERSION}-${archive_arch}-unknown-linux-musl.tar.gz"; \
    curl -fsSL \
      "https://github.com/quietvoid/dovi_tool/releases/download/${DOVI_TOOL_VERSION}/${archive}" \
      -o "/tmp/${archive}"; \
    echo "${archive_sha}  /tmp/${archive}" | sha256sum -c -; \
    tar --no-same-owner -xzf "/tmp/${archive}" -C /usr/local/bin ./dovi_tool; \
    rm "/tmp/${archive}"; \
    dovi_tool --version

COPY backend/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/entrypoint.sh ./entrypoint.sh
COPY --from=frontend-build /frontend/dist ./frontend
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod +x ./entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
