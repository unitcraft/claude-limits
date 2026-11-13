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

    def test_weekly_one_percent_early_projects_honestly(self):
        # Owner's word 2026-10-31: 30 and 60 minutes of history now carry a forecast
        # (the floor is five minutes). The cost is accepted: one percent over half an
        # hour extrapolates LOUDLY over the remaining week -- 336% and 168% -- and
        # the projection honestly says so instead of showing nothing. The row's
        # severity stays normal (the fill is 1%); the projection's own thresholds
        # govern the ghost.
        for span, want in ((1800, 336.0), (3600, 168.0)):
            with self.subTest(span=span):
                fr = self.forecast("weekly", span)
                self.assertIsNotNone(fr)
                pct_at_reset, runs_out, rate_h, span_min = fr
                self.assertEqual(pct_at_reset, want)
                self.assertIsNotNone(runs_out)   # it runs out before the reset

    def test_the_five_minute_floor_for_every_window_class(self):
        # Owner's word 2026-10-31 ("уменьши до 5 минут"): the old
        # max(30 min, window/20) became FIVE MINUTES flat, the same for session,
        # weekly and monthly -- the window's own length no longer raises it.
        for kind in ("session", "weekly", "monthly"):
            for working in (False, True):
                with self.subTest(kind=kind, working=working):
                    self.assertIsNone(self.forecast(kind, 299, working=working))
                    self.assertIsNotNone(self.forecast(kind, 300, working=working))

    def test_window_length_no_longer_raises_the_floor(self):
        # Same word: a month window and a week window stand on the same five minutes.
        self.assertIsNone(self.forecast("monthly", 299, window=2678400))
        self.assertIsNotNone(self.forecast("monthly", 300, window=2678400))
        self.assertIsNone(self.forecast("weekly", 299, window=604801))
        self.assertIsNotNone(self.forecast("weekly", 300, window=604801))

    def test_actual_codex_duration_still_feeds_the_window(self):
        usage = {"rate_limit": {"primary_window": {"limit_window_seconds": 2678400, "used_percent": 1,
                                                   "reset_at": self.NOW + 2678400 - 129600}}}
        row = next(ref.codex_rows_of(usage))
        self.assertEqual(row[1], 1)
        duration = ref.codex_window_seconds(usage, row[0])
        self.assertEqual(duration, 2678400)
        # The duration no longer gates the forecast, but it still shapes the rate's
        # window: over 36 hours one percent is a slow pace, not the floor's business.
        self.assertIsNotNone(self.forecast("monthly", 129600, window=duration))

    def test_qoder_quota_row_forecasts_as_a_month(self):
        # Task 035: the one quota row rides the month class -- the SUM against the
        # plan's month (usageType "credits"), reset = expiresAt -- so the forecast
        # machinery that serves Kimi's month serves Qoder's series too. The wire
        # (measured 2026-11-12): totalUsagePercentage is a FRACTION, expiresAt is ms.
        usage = {"totalUsagePercentage": 0.0566,
                 "expiresAt": (self.NOW + 30 * 86400) * 1000}
        kind, pct, _sev, _reset, reset_epoch = next(ref.qoder_rows_of(usage))
        self.assertEqual(kind, "quota")
        self.assertAlmostEqual(pct, 5.66, places=6)
        self.assertEqual(reset_epoch, self.NOW + 30 * 86400)
        self.assertEqual(ref.kind_class_of(kind), "monthly")
        sched = ref.forecast_config_of({})
        history = {"qoder:me@example.com|quota": [
            [self.NOW - 3 * 86400, 85], [self.NOW - 86400, 98],  # old month's tail
            [self.NOW - 86400 + 300, 0],                         # the observed reset
            [self.NOW, 5.66],
        ]}
        fr = ref.forecast_of(history, "qoder:me@example.com|quota",
                             ref.kind_class_of(kind), pct, reset_epoch, self.NOW, sched)
        self.assertIsNotNone(fr)
        self.assertGreater(fr[0], 100)

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

    def test_monthly_reset_seen_in_history_beats_arithmetic_window(self):
        # 2026-10-21: Kimi's month reset 36 h ago and resets_at is 30.4 d ahead,
        # so resets_at - 30 d lands in the FUTURE and no post-reset sample exists.
        sched = ref.forecast_config_of({})
        reset = self.NOW + 30 * 86400
        history = {"series": [
            [self.NOW - 3 * 86400, 85], [self.NOW - 86400, 98],  # old month's tail
            [self.NOW - 86400 + 300, 0],                          # the observed reset
            [self.NOW, 5.66],
        ]}
        fr = ref.forecast_of(history, "series", "monthly", 5.66, reset, self.NOW, sched)
        self.assertIsNotNone(fr)
        self.assertGreater(fr[0], 100)

    def test_monthly_without_observed_reset_still_waits(self):
        sched = ref.forecast_config_of({})
        reset = self.NOW + 30 * 86400
        history = {"series": [[self.NOW - 3600, 5.0], [self.NOW, 5.66]]}  # no drop visible
        self.assertIsNone(ref.forecast_of(history, "series", "monthly", 5.66, reset, self.NOW, sched))


if __name__ == "__main__":
    unittest.main()
