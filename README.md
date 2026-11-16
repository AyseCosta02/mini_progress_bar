# mini_progress_bar

A progress bar that stays readable when its output is redirected to a file or pipe.

```python
import sys
from mini_progress_bar import ProgressBar

with ProgressBar(total=100, stream=sys.stderr) as bar:
    for _ in range(100):
        # do work
        bar.update()
```

## Why this exists

Most progress bars assume a terminal: they write a carriage return, overwrite the same line,
and finish with a newline. Redirect that to a file and you get one enormous line, or a stream
of carriage returns that no text editor renders sensibly. `mini_progress_bar` checks whether
the stream is a TTY once, at construction time, and chooses its output format accordingly:
TTY streams get carriage-return updates, non-TTY streams get newline-terminated lines.

The trade-off is that non-TTY output is more verbose. A bar updated in a tight loop can flood
a log file with lines, so the constructor takes `min_interval` (default 0.1 seconds) to throttle
intermediate writes. The final write from `finish()` always goes through, so the last line
reflects the true final state even if throttling suppressed the updates before it.

## API

The package exports three names:

- `ProgressBar(total=None, stream=None, *, width=30, prefix="", suffix="", min_interval=0.1, clock=time.monotonic)`
  - `total` is the number of steps, or `None` for an unknown total.
  - `stream` defaults to `sys.stderr` so progress output does not pollute a program's stdout.
  - `update(step=1)` advances by `step`; `set(current)` jumps to an absolute value; `finish()` writes the final line and closes the bar. `finish()` is idempotent, and `update`/`set` raise `RuntimeError` after it.
  - The object is a context manager; leaving the `with` block calls `finish()`.
- `format_line(current, total, width=30, prefix="", suffix="")` returns the line as a string.
- `render_line(current, total, stream, *, width=30, prefix="", suffix="", is_tty=None)` writes one line to `stream`; pass `is_tty` to override detection.

## Edge case to know about

TTY detection happens once, in `__init__`, by calling `stream.isatty()` if it exists. A stream
without an `isatty` method (such as `io.StringIO`) is treated as non-TTY. If you replace a
`ProgressBar`'s stream after construction, the cached decision is not revisited.
