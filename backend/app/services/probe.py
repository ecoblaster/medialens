from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from app.services.scan_progress import set_scan_stage


class ProbeError(RuntimeError):
    """Raised when an external media probe command fails."""


class ProbeCancelled(ProbeError):
    """Raised when an active media probe is cancelled."""


@dataclass(frozen=True)
class ProbeResult:
    ffprobe: dict[str, Any]
    mediainfo: dict[str, Any]
    ffprobe_version: str | None = None
    mediainfo_version: str | None = None


_operation_context = threading.local()
_operation_lock = threading.Lock()
_active_processes: dict[str, subprocess.Popen[str]] = {}
_cancelled_operations: set[str] = set()


@contextmanager
def probe_operation(operation_id: str) -> Iterator[None]:
    previous = getattr(_operation_context, "operation_id", None)
    _operation_context.operation_id = operation_id
    try:
        yield
    finally:
        _operation_context.operation_id = previous


def cancel_probe_operation(operation_id: str) -> None:
    """Permanently flag this operation and interrupt any active subprocess."""
    with _operation_lock:
        _cancelled_operations.add(operation_id)
        process = _active_processes.get(operation_id)
    if process is not None:
        _stop_process(process)


def finish_probe_operation(operation_id: str) -> None:
    # Keep the cancellation flag until the worker has fully exited. This closes
    # the race where one probe ends just before another native command starts.
    with _operation_lock:
        process = _active_processes.pop(operation_id, None)
        _cancelled_operations.discard(operation_id)
    if process is not None:
        _stop_process(process)


def _operation_id() -> str | None:
    return getattr(_operation_context, "operation_id", None)


def _is_cancelled(operation_id: str | None) -> bool:
    if operation_id is None:
        return False
    with _operation_lock:
        return operation_id in _cancelled_operations


def _stage(label: str) -> None:
    operation_id = _operation_id()
    if operation_id is not None:
        set_scan_stage(operation_id, label)


def _signal_process(process: subprocess.Popen[str], sig: signal.Signals) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except (ProcessLookupError, PermissionError):
        return
    except OSError:
        try:
            process.terminate() if sig == signal.SIGTERM else process.kill()
        except ProcessLookupError:
            pass


def _stop_process(process: subprocess.Popen[str]) -> None:
    _signal_process(process, signal.SIGTERM)
    try:
        process.wait(timeout=1)
        return
    except subprocess.TimeoutExpired:
        pass
    _signal_process(process, signal.SIGKILL)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def _register_process(operation_id: str | None, process: subprocess.Popen[str]) -> None:
    if operation_id is None:
        return
    cancelled = False
    with _operation_lock:
        cancelled = operation_id in _cancelled_operations
        if not cancelled:
            _active_processes[operation_id] = process
    if cancelled:
        _stop_process(process)
        raise ProbeCancelled("Probe was cancelled before the native tool started.")


def _unregister_process(operation_id: str | None, process: subprocess.Popen[str]) -> None:
    if operation_id is None:
        return
    with _operation_lock:
        if _active_processes.get(operation_id) is process:
            _active_processes.pop(operation_id, None)


def _run_command(command: list[str], tool_name: str, *, timeout: int) -> subprocess.CompletedProcess[str]:
    operation_id = _operation_id()
    if _is_cancelled(operation_id):
        raise ProbeCancelled(f"{tool_name} was cancelled.")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ProbeError(f"{tool_name} is not installed in the MediaLens container.") from exc

    try:
        _register_process(operation_id, process)
    except ProbeCancelled:
        raise

    deadline = time.monotonic() + timeout
    stdout = ""
    stderr = ""
    try:
        while True:
            if _is_cancelled(operation_id):
                _stop_process(process)
                raise ProbeCancelled(f"{tool_name} was cancelled.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_process(process)
                raise ProbeError(f"{tool_name} timed out after {timeout} seconds while analyzing the file.")
            try:
                stdout, stderr = process.communicate(timeout=min(0.25, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        _unregister_process(operation_id, process)

    if _is_cancelled(operation_id):
        raise ProbeCancelled(f"{tool_name} was cancelled.")
    if process.returncode != 0:
        message = stderr.strip() or stdout.strip() or "Unknown probe error"
        raise ProbeError(f"{tool_name} failed: {message}")
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _run_json_command(command: list[str], tool_name: str, *, timeout: int) -> dict[str, Any]:
    result = _run_command(command, tool_name, timeout=timeout)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"{tool_name} returned invalid JSON output.") from exc
    if not isinstance(payload, dict):
        raise ProbeError(f"{tool_name} returned an unexpected JSON structure.")
    return payload


def _run_text_command(command: list[str], tool_name: str, *, timeout: int) -> str:
    return _run_command(command, tool_name, timeout=timeout).stdout.strip()


def _tool_version(command: list[str]) -> str | None:
    operation_id = _operation_id()
    if _is_cancelled(operation_id):
        raise ProbeCancelled("Probe version check was cancelled.")
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None


def _duration_seconds(ffprobe: dict[str, Any]) -> float | None:
    format_data = ffprobe.get("format")
    if not isinstance(format_data, dict):
        return None
    try:
        duration = float(str(format_data.get("duration")))
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def _needs_dynamic_hdr_probe(ffprobe: dict[str, Any]) -> bool:
    streams = ffprobe.get("streams")
    if not isinstance(streams, list):
        return False
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "video":
            continue
        codec = str(stream.get("codec_name") or "").lower()
        transfer = str(stream.get("color_transfer") or "").lower()
        if codec in {"hevc", "h265", "av1"} and transfer in {"smpte2084", "pq"}:
            return True
    return False


def _hdr_sample_intervals(duration: float | None) -> str:
    if duration is None or duration < 4:
        return "%+#64"
    starts = [0.0, duration * 0.10, duration * 0.50, duration * 0.90]
    unique_starts = list(dict.fromkeys(round(start, 3) for start in starts))
    return ",".join(f"{start:.3f}%+#16" for start in unique_starts)


def _optional_json(command: list[str], tool_name: str, *, timeout: int) -> tuple[dict[str, Any], str | None]:
    try:
        return _run_json_command(command, tool_name, timeout=timeout), None
    except ProbeCancelled:
        raise
    except ProbeError as exc:
        return {}, str(exc)


def _probe_dynamic_hdr(path: Path, ffprobe: dict[str, Any]) -> dict[str, Any]:
    intervals = _hdr_sample_intervals(_duration_seconds(ffprobe))
    common = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", intervals, "-print_format", "json"]
    _stage("HDR10+ packet analysis")
    packet_payload, packet_error = _optional_json([*common, "-show_packets", str(path)], "ffprobe HDR packet probe", timeout=20)
    _stage("HDR10+ frame analysis")
    frame_payload, frame_error = _optional_json([*common, "-show_frames", str(path)], "ffprobe HDR frame probe", timeout=20)
    result: dict[str, Any] = {
        "intervals": intervals,
        "packets": packet_payload.get("packets") if isinstance(packet_payload.get("packets"), list) else [],
        "frames": frame_payload.get("frames") if isinstance(frame_payload.get("frames"), list) else [],
    }
    if packet_error:
        result["packet_error"] = packet_error
    if frame_error:
        result["frame_error"] = frame_error
    return result


def _mediainfo_hdr_summary(path: Path) -> str:
    fields = "%HDR_Format%|%HDR_Format_Compatibility%|%HDR_Format_Commercial%|%HDR_Format_String%|%HDR_Format_Profile%|%HDR_Format_Settings%"
    try:
        _stage("Reading HDR metadata")
        return _run_text_command(["mediainfo", f"--Inform=Video;{fields}", str(path)], "MediaInfo HDR summary", timeout=15)
    except ProbeCancelled:
        raise
    except ProbeError as exc:
        return f"probe-error: {exc}"


def probe_media(path: Path) -> ProbeResult:
    _stage("Reading container and streams")
    ffprobe = _run_json_command(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", "-show_chapters", str(path)],
        "ffprobe",
        timeout=45,
    )
    _stage("Reading detailed MediaInfo")
    mediainfo = _run_json_command(["mediainfo", "--Full", "--Output=JSON", str(path)], "MediaInfo", timeout=45)
    mediainfo["medialens_hdr_summary"] = _mediainfo_hdr_summary(path)
    if _needs_dynamic_hdr_probe(ffprobe):
        ffprobe["medialens_hdr10_plus_probe"] = _probe_dynamic_hdr(path, ffprobe)
    _stage("Reading probe versions")
    return ProbeResult(
        ffprobe=ffprobe,
        mediainfo=mediainfo,
        ffprobe_version=_tool_version(["ffprobe", "-version"]),
        mediainfo_version=_tool_version(["mediainfo", "--Version"]),
    )
