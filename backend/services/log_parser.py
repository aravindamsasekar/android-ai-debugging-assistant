"""Simple crash log parser for Android stack traces."""

import re

SUPPORTED_EXCEPTIONS = (
    "NullPointerException",
    "SocketTimeoutException",
    "IllegalStateException",
)

_LOG_KEYWORDS = ("Exception", "Caused by", "FATAL", "Error")
_KOTLIN_LOCATION_RE = re.compile(r"(\w+\.kt):(\d+)")
_APP_FRAME_RE = re.compile(r"at com\.example\.\S+\((\w+\.kt):(\d+)\)")


def _find_exception_type(log_text: str) -> str | None:
    for line in log_text.splitlines():
        for exception_type in SUPPORTED_EXCEPTIONS:
            if exception_type in line:
                return exception_type
    return None


def _find_crash_location(log_text: str) -> tuple[str | None, int | None]:
    for line in log_text.splitlines():
        match = _APP_FRAME_RE.search(line)
        if match:
            return match.group(1), int(match.group(2))

    for line in log_text.splitlines():
        match = _KOTLIN_LOCATION_RE.search(line)
        if match:
            return match.group(1), int(match.group(2))

    return None, None


def _find_important_line(log_text: str) -> str | None:
    for line in log_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(keyword in stripped for keyword in _LOG_KEYWORDS):
            return stripped

    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    return lines[0] if lines else None


def parse_log(log_text: str) -> dict:
    crash_file, crash_line = _find_crash_location(log_text)
    return {
        "exceptionType": _find_exception_type(log_text),
        "crashFile": crash_file,
        "crashLine": crash_line,
        "importantLine": _find_important_line(log_text),
    }
