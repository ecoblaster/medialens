# MediaLens development setup

MediaLens v0.2 adds the first real media scanner. It can analyze one file from a
registered filesystem library with `ffprobe` and MediaInfo, store its video,
audio, and subtitle streams, and return the result through the API.

## Current capabilities

- FastAPI application and SQLite persistence
- Library CRUD endpoints
- Single-file scans using a safe relative path
- `ffprobe` and MediaInfo installed in the container
- Video codec, resolution, bit depth, frame rate, and HDR detection
- Dolby Vision profile detection when exposed by `ffprobe`
- Audio codec and Atmos/DTS:X classification
- Subtitle format and text/image classification
- Raw probe snapshots for diagnostics
- Unchanged-file detection using size and modification time
- Read-only media mounts

FEL versus MEL classification still requires `dovi_tool`. Until that integration
is added, files with a Dolby Vision enhancement layer are reported as
`el_type: "UNKNOWN"` rather than guessed.

## Start or update MediaLens

From the repository root:

```bash
git pull
docker compose down
docker compose up -d --build
```

Open:

- API documentation: <http://YOUR-UNRAID-IP:8090/docs>
- Health check: <http://YOUR-UNRAID-IP:8090/api/v1/health>

The Docker health check uses port 8080 internally. Port 8090 is the default
host-side port and can be changed with `MEDIALENS_HOST_PORT`.

## Register the libraries

Use the container paths from `docker-compose.yml`, not the original Unraid host
paths.

Movies:

```json
{
  "name": "Movies",
  "media_kind": "movies",
  "source_type": "filesystem",
  "root_path": "/media/movies",
  "external_id": null,
  "enabled": true
}
```

TV:

```json
{
  "name": "TV Shows",
  "media_kind": "tv",
  "source_type": "filesystem",
  "root_path": "/media/tv",
  "external_id": null,
  "enabled": true
}
```

## Scan one file

In Swagger, use `POST /api/v1/scans`. Supply the library UUID returned by
`GET /api/v1/libraries` and a path relative to that library's container root.

Example:

```json
{
  "library_id": "YOUR-LIBRARY-UUID",
  "mode": "single_file",
  "relative_path": "Dune (2021)/Dune (2021).mkv",
  "force": false
}
```

The scan response contains a `media_file_id`. Use it with:

```text
GET /api/v1/files/{file_id}
```

That response contains the normalized video, audio, subtitle, HDR, and Dolby
Vision information.

Set `force` to `true` to analyze the file again even if its size and
modification timestamp have not changed.

## Run tests

```bash
docker compose run --rm api pytest -q
```

## Migration workflow

This version uses the existing initial schema and does not add a new migration.
Apply committed migrations with:

```bash
docker compose run --rm api alembic upgrade head
```
