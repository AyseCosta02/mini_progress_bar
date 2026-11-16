import io
import unittest

from mini_progress_bar import ProgressBar, format_line, render_line


class FakeClock:
    """Deterministic clock: each call returns the next value in the list."""

    def __init__(self, values):
        self._values = list(values)
        self._index = 0

    def __call__(self):
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


class FormatLineTests(unittest.TestCase):
    def test_known_total(self):
        self.assertEqual(format_line(5, 10, width=10), "[#####-----]  50% 5/10")

    def test_zero_total_is_complete(self):
        self.assertEqual(format_line(0, 0, width=10), "[##########] 100% 0/0")

    def test_current_clamped_to_total(self):
        self.assertEqual(format_line(20, 10, width=10), "[##########] 100% 10/10")

    def test_negative_current_clamped_to_zero(self):
        self.assertEqual(format_line(-3, 10, width=10), "[----------]   0% 0/10")

    def test_unknown_total(self):
        self.assertEqual(format_line(7, None, width=5), "[#####] 7")

    def test_prefix_and_suffix(self):
        self.assertEqual(
            format_line(1, 2, width=4, prefix="p ", suffix=" s"),
            "p [##--]  50% 1/2 s",
        )

    def test_width_must_be_positive(self):
        with self.assertRaises(ValueError):
            format_line(1, 2, width=0)

    def test_negative_total_rejected(self):
        with self.assertRaises(ValueError):
            format_line(1, -2)


class RenderLineTests(unittest.TestCase):
    def test_non_tty_writes_newline_terminated_line(self):
        stream = io.StringIO()
        render_line(1, 2, stream, width=4, is_tty=False)
        self.assertEqual(stream.getvalue(), "[##--]  50% 1/2\n")

    def test_tty_writes_carriage_return_without_newline(self):
        stream = io.StringIO()
        render_line(1, 2, stream, width=4, is_tty=True)
        self.assertEqual(stream.getvalue(), "\r[##--]  50% 1/2")

    def test_stream_without_isatty_is_treated_as_non_tty(self):
        stream = io.StringIO()
        render_line(1, 2, stream, width=4)
        self.assertEqual(stream.getvalue(), "[##--]  50% 1/2\n")


class ProgressBarTests(unittest.TestCase):
    def test_non_tty_writes_one_line_per_update(self):
        stream = io.StringIO()
        bar = ProgressBar(total=2, stream=stream, width=4, min_interval=0)
        bar.update()
        bar.update()
        bar.finish()
        self.assertEqual(
            stream.getvalue(),
            "[##--]  50% 1/2\n" "[####] 100% 2/2\n" "[####] 100% 2/2\n",
        )

    def test_tty_finish_adds_trailing_newline(self):
        stream = io.StringIO()
        bar = ProgressBar(total=2, stream=stream, width=4, min_interval=0)
        bar._is_tty = True
        bar.update()
        bar.finish()
        self.assertEqual(stream.getvalue(), "\r[##--]  50% 1/2\r[####] 100% 2/2\n")

    def test_finish_sets_current_to_total(self):
        stream = io.StringIO()
        bar = ProgressBar(total=10, stream=stream, width=4, min_interval=0)
        bar.set(3)
        bar.finish()
        lines = stream.getvalue().splitlines()
        self.assertEqual(lines[-1], "[####] 100% 10/10")

    def test_finish_is_idempotent(self):
        stream = io.StringIO()
        bar = ProgressBar(total=1, stream=stream, width=4, min_interval=0)
        bar.finish()
        first = stream.getvalue()
        bar.finish()
        self.assertEqual(stream.getvalue(), first)

    def test_update_after_finish_raises(self):
        stream = io.StringIO()
        bar = ProgressBar(total=1, stream=stream, width=4, min_interval=0)
        bar.finish()
        with self.assertRaises(RuntimeError):
            bar.update()

    def test_min_interval_throttles_with_fake_clock(self):
        stream = io.StringIO()
        clock = FakeClock([0.0, 0.05, 0.2])
        bar = ProgressBar(total=3, stream=stream, width=4, min_interval=0.1, clock=clock)
        bar.update()  # writes at t=0.0
        bar.update()  # t=0.05, throttled
        bar.update()  # t=0.2, writes
        self.assertEqual(
            stream.getvalue(),
            "[#---]  33% 1/3\n" "[###-]  67% 2/3\n",
        )

    def test_finish_bypasses_throttle(self):
        stream = io.StringIO()
        clock = FakeClock([0.0, 0.01, 0.01])
        bar = ProgressBar(total=2, stream=stream, width=4, min_interval=1.0, clock=clock)
        bar.update()
        bar.finish()
        self.assertEqual(
            stream.getvalue(),
            "[##--]  50% 1/2\n" "[####] 100% 2/2\n",
        )

    def test_set_clamps_to_total(self):
        stream = io.StringIO()
        bar = ProgressBar(total=5, stream=stream, width=4, min_interval=0)
        bar.set(99)
        self.assertEqual(stream.getvalue(), "[####] 100% 5/5\n")

    def test_unknown_total_renders_indeterminate(self):
        stream = io.StringIO()
        bar = ProgressBar(total=None, stream=stream, width=4, min_interval=0)
        bar.update(3)
        bar.finish()
        self.assertEqual(stream.getvalue(), "[####] 3\n" "[####] 3\n")

    def test_context_manager_finishes(self):
        stream = io.StringIO()
        with ProgressBar(total=1, stream=stream, width=4, min_interval=0) as bar:
            bar.update()
        self.assertEqual(stream.getvalue(), "[####] 100% 1/1\n" "[####] 100% 1/1\n")

    def test_invalid_arguments_rejected(self):
        with self.assertRaises(ValueError):
            ProgressBar(total=-1)
        with self.assertRaises(ValueError):
            ProgressBar(total=1, width=0)
        with self.assertRaises(ValueError):
            ProgressBar(total=1, min_interval=-0.1)


if __name__ == "__main__":
    unittest.main()
