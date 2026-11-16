"""Core progress bar implementation.

Design decisions:
- The bar writes a carriage-return-updated line to a stream. When the stream is a TTY
  it uses ``\r`` to overwrite the previous line. When the stream is not a TTY (e.g. a
  file or pipe) it writes newline-terminated lines instead, so redirecting output does
  not produce a single long overwritten line.
- A ``min_interval`` throttles non-final updates to avoid flooding a file with lines
  when the bar is updated in a tight loop. The final update is always written.
- A caller-supplied clock makes the throttle testable without sleeping.
"""

from __future__ import annotations

import sys
import time
from typing import Callable, IO, Optional


def format_line(
    current: int,
    total: Optional[int],
    width: int = 30,
    prefix: str = "",
    suffix: str = "",
) -> str:
    """Return a single progress line as a string.

    ``total`` may be ``None`` for an unknown total, in which case the bar is rendered
    as an indeterminate full-width block and the percentage is omitted. ``current`` is
    clamped to ``[0, total]`` when ``total`` is known so an over-count cannot produce a
    bar wider than ``width``.
    """
    if width < 1:
        raise ValueError("width must be at least 1")

    if total is None:
        bar = "[" + "#" * width + "]"
        return "{}{} {}{}".format(prefix, bar, current, suffix)

    if total < 0:
        raise ValueError("total must be non-negative or None")

    clamped = max(0, min(current, total))
    if total == 0:
        fraction = 1.0
    else:
        fraction = clamped / total

    filled = int(round(fraction * width))
    filled = max(0, min(width, filled))
    bar = "[" + "#" * filled + "-" * (width - filled) + "]"
    percent = int(round(fraction * 100))
    return "{}{} {:3d}% {}/{}{}".format(prefix, bar, percent, clamped, total, suffix)


def render_line(
    current: int,
    total: Optional[int],
    stream: IO[str],
    *,
    width: int = 30,
    prefix: str = "",
    suffix: str = "",
    is_tty: Optional[bool] = None,
) -> None:
    """Write one progress line to ``stream``.

    If ``is_tty`` is ``None`` the stream's ``isatty`` is consulted; a stream without
    that method (e.g. ``io.StringIO``) is treated as non-TTY. TTY output is prefixed
    with ``\r`` and not newline-terminated; non-TTY output is newline-terminated.
    """
    if is_tty is None:
        isatty = getattr(stream, "isatty", None)
        is_tty = bool(isatty()) if callable(isatty) else False

    line = format_line(current, total, width=width, prefix=prefix, suffix=suffix)
    if is_tty:
        stream.write("\r" + line)
    else:
        stream.write(line + "\n")
    stream.flush()


class ProgressBar:
    """A progress bar that remains readable when output is redirected.

    Parameters
    ----------
    total:
        Number of steps, or ``None`` for an unknown total.
    stream:
        Destination for output. Defaults to ``sys.stderr``. ``sys.stderr`` is the
        default because progress output should not pollute a program's stdout data.
    width:
        Width of the bar in characters.
    prefix, suffix:
        Text placed before and after the bar.
    min_interval:
        Minimum seconds between non-final writes. ``0`` disables throttling.
    clock:
        Callable returning monotonic seconds. Override in tests to avoid sleeping.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        stream: Optional[IO[str]] = None,
        *,
        width: int = 30,
        prefix: str = "",
        suffix: str = "",
        min_interval: float = 0.1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if total is not None and total < 0:
            raise ValueError("total must be non-negative or None")
        if width < 1:
            raise ValueError("width must be at least 1")
        if min_interval < 0:
            raise ValueError("min_interval must be non-negative")

        self.total = total
        self.stream = stream if stream is not None else sys.stderr
        self.width = width
        self.prefix = prefix
        self.suffix = suffix
        self.min_interval = min_interval
        self._clock = clock
        self.current = 0
        self._last_write = None
        self._closed = False

        isatty = getattr(self.stream, "isatty", None)
        self._is_tty = bool(isatty()) if callable(isatty) else False

    def _should_write(self, force: bool) -> bool:
        if force or self.min_interval == 0:
            return True
        now = self._clock()
        if self._last_write is None or now - self._last_write >= self.min_interval:
            return True
        return False

    def _write(self, force: bool) -> None:
        if self._closed and not force:
            return
        if not self._should_write(force):
            return
        render_line(
            self.current,
            self.total,
            self.stream,
            width=self.width,
            prefix=self.prefix,
            suffix=self.suffix,
            is_tty=self._is_tty,
        )
        self._last_write = self._clock()

    def update(self, step: int = 1) -> None:
        """Advance the bar by ``step`` and write if the throttle allows."""
        if self._closed:
            raise RuntimeError("cannot update a closed progress bar")
        self.current += step
        if self.total is not None and self.current > self.total:
            self.current = self.total
        self._write(force=False)

    def set(self, current: int) -> None:
        """Set the bar to an absolute ``current`` value and write if allowed."""
        if self._closed:
            raise RuntimeError("cannot update a closed progress bar")
        self.current = current
        if self.total is not None and self.current > self.total:
            self.current = self.total
        self._write(force=False)

    def finish(self) -> None:
        """Write a final line and mark the bar closed. Idempotent."""
        if self._closed:
            return
        if self.total is not None:
            self.current = self.total
        self._write(force=True)
        if self._is_tty:
            self.stream.write("\n")
            self.stream.flush()
        self._closed = True

    def __enter__(self) -> "ProgressBar":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.finish()
