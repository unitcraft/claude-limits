"""Offline forecast sufficiency regressions; python -m unittest discover -s scripts -p test_forecast.py."""
import contextlib
import io
import unittest

import claude_limits as ref


class ForecastHistoryTest(unittest.TestCase):
    NOW = 1790845200  # Thursday 09:00 UTC

    def forecast(self, kind, span, *, age=None, working=False, window=None, extra=()):
        duration = window or {"session": 18000, "weekly": 604800, "monthly": 2592000}[kind]
        reset = self.NOW + duration - (age if age is not None else span)
        history = {"series": [*extra, [self.NOW - span, 0], [self.NOW, 1]]}
        sched = ref.forecast_config_of({"forecast": {"working_hours": working, "off_hours_rate": 100}})
        return ref.forecast_of(history, "series", kind, 1, reset, self.NOW, sched, window)

    def test_weekly_one_percent_early_is_not_a_critical_projection(self):
        for span in (1800, 3600):
            with self.subTest(span=span):
                fr = self.forecast("weekly", span)
                self.assertIsNone(fr)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    ref.print_limit_row("weekly limit", 1, None, "resets later", fr, ref.Paint(False), "ascii")
                self.assertIn("1%", out.getvalue())
                self.assertNotIn("at reset", out.getvalue())
                self.assertEqual(ref.severity_of(None, 1), "normal")

    def test_exact_boundaries_for_both_time_bases(self):
        for kind, minimum in (("session", 1800), ("weekly", 30240), ("monthly", 129600)):
            for working in (False, True):
                with self.subTest(kind=kind, working=working):
                    self.assertIsNone(self.forecast(kind, minimum - 1, working=working))
                    self.assertIsNotNone(self.forecast(kind, minimum, working=working))

    def test_old_window_and_previous_window_do_not_supply_history(self):
        self.assertIsNone(self.forecast("weekly", 1800, age=86400))
        self.assertIsNone(self.forecast("weekly", 1800, extra=((self.NOW - 604800, 0),)))
        self.assertIsNone(self.forecast("monthly", 3600, age=10 * 86400))

    def test_actual_codex_duration_and_ceil(self):
        usage = {"rate_limit": {"primary_window": {"limit_window_seconds": 2678400, "used_percent": 1,
                                                   "reset_at": self.NOW + 2678400 - 129600}}}
        row = next(ref.codex_rows_of(usage))
        self.assertEqual(row[1], 1)
        duration = ref.codex_window_seconds(usage, row[0])
        self.assertEqual(duration, 2678400)
        self.assertIsNone(self.forecast("monthly", 129600, window=duration))
        self.assertIsNotNone(self.forecast("monthly", 133920, window=duration))
        self.assertIsNone(self.forecast("weekly", 30240, window=604801))
        self.assertIsNotNone(self.forecast("weekly", 30241, window=604801))

    def test_missing_reset_history_or_percent(self):
        sched = ref.forecast_config_of({})
        for reset in (None, self.NOW, self.NOW - 1):
            self.assertIsNone(ref.forecast_of({}, "series", "weekly", 1, reset, self.NOW, sched))
        self.assertIsNone(ref.forecast_of({}, "series", "weekly", 1, self.NOW + 86400, self.NOW, sched))
        self.assertIsNone(ref.forecast_of({}, "series", "weekly", None, self.NOW + 86400, self.NOW, sched))

    def test_mature_forecasts_and_flat_rate_still_work(self):
        self.assertIsNotNone(self.forecast("weekly", 2 * 86400))
        sched = ref.forecast_config_of({})
        history = {"series": [[self.NOW - 1800, 1], [self.NOW, 1]]}
        self.assertEqual(ref.forecast_of(history, "series", "session", 1, self.NOW + 3600, self.NOW, sched)[0], 1)


if __name__ == "__main__":
    unittest.main()
