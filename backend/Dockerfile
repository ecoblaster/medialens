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

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MEDIALENS_APP_VERSION=${MEDIALENS_BUILD_VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl ffmpeg mediainfo \
    && rm -rf /var/lib/apt/lists/*

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
