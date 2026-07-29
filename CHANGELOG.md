# Changelog

## 1.0.0 — 2026-07-29

First stable MediaLens release.

### Library analysis

- Recursive movie and TV library scanning
- FFprobe and MediaInfo metadata collection
- Dolby Vision profile detection
- HDR10, HDR10+, HLG, SDR, and unknown-HDR reporting
- Dolby Atmos, DTS:X, codec, channel, subtitle, resolution, bitrate, and size analysis
- Full-library media browser and database-backed search

### Hardware compatibility

- Direct Play, remux, audio-transcode, video-transcode, unsupported, and unknown outcomes
- NVIDIA Shield TV Pro, Apple TV 4K, and Fire TV Cube profiles
- Ugoos AM6B Plus/CoreELEC, SK1, AM8 Pro, AM9 Pro, and SK4 Pro profiles
- Per-file compatibility explanations and library summaries

### Automatic scanning

- Recursive filesystem watcher for new, changed, renamed, and deleted files
- File-copy stability delay before analysis
- Periodic reconciliation for missed filesystem events and Unraid user shares
- Duplicate-event suppression and serialized automatic scans
- Sample, temporary, and release-group promotional file filtering
- Automatic metadata cleanup for removed source files

### Reliability

- Cancellable probes and full-library scans
- Persistent progress counters, ETA, and current-file reporting
- Worker crash detection and restart recovery
- Stream replacement ordering fixes for SQLite uniqueness constraints
- Verified persistence of brand-new single-file imports before reporting completion

### Interface

- Dark responsive dashboard
- Library health filters
- Bundled Dolby Vision, HDR10+, and Dolby Atmos logos
- MediaLens favicon
- Automatic watcher status and activity panel

### Container release

- Docker Hub image: `ecoblaster/medialens:1.0.0`
- GitHub Container Registry mirror: `ghcr.io/ecoblaster/medialens:1.0.0`
- Linux `amd64` and `arm64` publishing workflow
