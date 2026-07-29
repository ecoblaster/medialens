# MediaLens

MediaLens is a read-only media library analyzer for movies and TV shows. It scans local media with FFprobe and MediaInfo, presents HDR and audio capability information, evaluates playback-device compatibility, and automatically imports new files after they finish copying.

## MediaLens 1.1.0

The stable image is published as:

```text
ecoblaster/medialens:1.1.0
ecoblaster/medialens:latest
```

A GitHub Container Registry mirror is also available:

```text
ghcr.io/ecoblaster/medialens:1.1.0
ghcr.io/ecoblaster/medialens:latest
```

## Docker run

```bash
docker run -d \
  --name medialens \
  --restart unless-stopped \
  -p 8090:8080 \
  -e MEDIALENS_AUTO_SCAN_ENABLED=true \
  -e MEDIALENS_FILE_STABILITY_SECONDS=60 \
  -e MEDIALENS_RECONCILE_MINUTES=15 \
  -v /mnt/user/appdata/medialens:/data \
  -v "/mnt/user/Media/Movies:/media/movies:ro" \
  -v "/mnt/user/Media/TV Shows:/media/tv:ro" \
  ecoblaster/medialens:1.1.0
```

Open MediaLens at `http://<server-address>:8090`.

## Docker Compose

Copy `docker-compose.production.yml`, then set the paths for your server:

```bash
export MEDIALENS_DATA_PATH=/mnt/user/appdata/medialens
export MEDIALENS_MOVIES_PATH="/mnt/user/Media/Movies"
export MEDIALENS_TV_PATH="/mnt/user/Media/TV Shows"
docker compose -f docker-compose.production.yml up -d
```

## Unraid template settings

Use these values when adding the container manually:

| Setting | Value |
|---|---|
| Repository | `ecoblaster/medialens:latest` |
| WebUI | `http://[IP]:[PORT:8080]` |
| Container port | `8080` |
| Suggested host port | `8090` |
| App data container path | `/data` |
| Movies container path | `/media/movies` (read-only) |
| TV container path | `/media/tv` (read-only) |

Using `latest` allows Unraid to detect newly published stable images. To pin the installation to a specific release instead, use a numbered tag such as `ecoblaster/medialens:1.1.0`; pinned containers must be changed manually when moving to a later version.

Recommended variables:

| Variable | Default |
|---|---|
| `MEDIALENS_AUTO_SCAN_ENABLED` | `true` |
| `MEDIALENS_FILE_STABILITY_SECONDS` | `60` |
| `MEDIALENS_RECONCILE_MINUTES` | `15` |

## First-run setup wizard

MediaLens 1.1 includes a guided setup wizard for empty installations.

1. Open `http://<server-address>:8090`.
2. Choose whether to add Movies, TV Shows, or both.
3. Confirm the prefilled container paths `/media/movies` and `/media/tv`.
4. Optionally change the library names or container paths.
5. Choose whether to begin the initial full scans immediately.
6. Finish setup and follow scan progress from the dashboard.

The wizard appears only when no libraries are registered. Existing installations that reuse the same `/data` mapping continue directly to the dashboard with their libraries and scan history intact.

Advanced library management remains available through the API documentation at `http://<server-address>:8090/docs`.

## Main features

- Guided first-run library setup
- Dolby Vision profile, HDR10, HDR10+, and SDR analysis
- Dolby Atmos, DTS:X, lossless audio, subtitle, bitrate, and codec analysis
- Hardware compatibility profiles for NVIDIA Shield, Apple TV, Fire TV Cube, and Ugoos devices
- Automatic scanning with file-copy stability checks and periodic reconciliation
- Full-library search and quality-health filters
- Read-only library mounts; MediaLens never modifies source media

## Data and upgrades

MediaLens stores its SQLite database under `/data`. Keep that directory persistent when recreating or upgrading the container.

For an Unraid installation using the `latest` tag:

1. Select **Check for Updates** on the Docker page.
2. Apply the MediaLens update when a new image is available.
3. Keep the existing `/data`, `/media/movies`, and `/media/tv` mappings unchanged.

For a command-line installation:

```bash
docker pull ecoblaster/medialens:latest
```

Then recreate the container while preserving the same `/data`, movie, and TV mappings.
