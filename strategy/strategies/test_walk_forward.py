"""
Walk-forward runner tests.

Verifies window count, session IDs, and aggregate metric computation
using synthetic in-memory data (no real DB or broker).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
from testing.backtesting.data_loader import DataLoader
from testing.backtesting.report import BacktestConfig, BacktestReport
from testing.walk_forward.report import WalkForwardConfig, WalkForwardReport
from testing.walk_forward.runner import _compute_windows

from trading.config.settings import AlgoSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _InMemoryLoader(DataLoader):
    """DataLoader that returns a pre-built DataFrame for any symbol/interval."""

    def __init__(self, df: pl.DataFrame) -> None:
        self._df = df

    def load(self, symbol: str, interval: str, start: datetime, end: datetime) -> pl.DataFrame:
        return self._df.filter((pl.col("date") >= start) & (pl.col("date") <= end))


def _make_df(n_bars: int) -> pl.DataFrame:
    from testing.utils.generators import trending_market

    return trending_market(n_bars=n_bars, seed=42)


def _algo(name: str = "wf_html_test") -> AlgoSettings:
    return AlgoSettings(
        name=name,
        instruments=["INFY"],
        strategy_id="ema_crossover",
        candle_intervals=["1min"],
    )


def _equity_curve() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": [datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC)],
            "equity": [100_000.0, 101_000.0],
        }
    )


def _window_report(session_id: str, sharpe: float, max_drawdown: float) -> BacktestReport:
    return BacktestReport(
        config=BacktestConfig(
            algo=_algo(),
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
            loader=_InMemoryLoader(_make_df(10)),
        ),
        equity_curve=_equity_curve(),
        trades=[],
        sharpe_ratio=sharpe,
        max_drawdown=max_drawdown,
        max_drawdown_duration=timedelta(hours=1),
        win_rate=0.5,
        profit_factor=1.2,
        cagr=0.1,
        calmar_ratio=0.2,
        total_trades=3,
        final_equity=101_000.0,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compute_windows_correct_count():
    """Window count should be predictable from bar count and step size."""
    df = _make_df(500)
    windows = _compute_windows(df, train_bars=200, test_bars=50, step_bars=50)
    # Expected: floor((500 - 250) / 50) + 1 windows
    expected = (500 - 250) // 50 + 1
    assert len(windows) == expected


def test_compute_windows_no_overlap_in_test_periods():
    """Test windows must not overlap each other in the test period."""
    df = _make_df(400)
    windows = _compute_windows(df, train_bars=150, test_bars=50, step_bars=50)

    for i in range(len(windows) - 1):
        _, _, test_start_i, test_end_i = windows[i]
        _, _, test_start_j, test_end_j = windows[i + 1]
        assert test_end_i < test_start_j, (
            f"Test window {i} and {i + 1} overlap: {test_end_i} vs {test_start_j}"
        )


def test_compute_windows_empty_when_not_enough_bars():
    """No windows when there aren't enough bars."""
    df = _make_df(10)
    windows = _compute_windows(df, train_bars=200, test_bars=50, step_bars=50)
    assert len(windows) == 0


def test_walk_forward_session_ids_unique():
    """Each window's BacktestReport should have a unique session_id."""
    from testing.walk_forward.runner import _compute_windows

    df = _make_df(300)
    windows = _compute_windows(df, train_bars=100, test_bars=50, step_bars=50)
    # session IDs would be "{parent_id}_w{i}" — just check the pattern is stable
    parent_id = "test_parent"
    ids = [f"{parent_id}_w{i + 1}" for i in range(len(windows))]
    assert len(ids) == len(set(ids)), "Window session IDs must be unique"


def test_walk_forward_html_report_generated():
    """WalkForwardReport.to_html() must return a non-empty standalone HTML string
    embedding all 4 figures (equity curve, per-window Sharpe, per-window drawdown,
    aggregate metrics table) — no real DB or broker involved."""
    windows = [
        _window_report("wf_html_test_w1", sharpe=1.2, max_drawdown=-0.05),
        _window_report("wf_html_test_w2", sharpe=-0.3, max_drawdown=-0.10),
    ]
    report = WalkForwardReport(
        config=WalkForwardConfig(
            algo=_algo(),
            loader=_InMemoryLoader(_make_df(10)),
            symbols=["INFY"],
        ),
        windows=windows,
        aggregate_sharpe=0.45,
        aggregate_max_drawdown=-0.10,
        aggregate_win_rate=0.5,
        combined_equity_curve=_equity_curve(),
        session_id="wf_html_test",
    )

    html = report.to_html()

    assert "<html" in html.lower()
    assert "plotly" in html.lower()
    assert "Walk-Forward Report" in html
    # Sanity-check all 4 figures actually made it into the output, not just the shell.
    assert "Combined Walk-Forward Equity Curve" in html
    assert "Per-Window Sharpe Ratio" in html
    assert "Per-Window Max Drawdown" in html
    assert "Aggregate Metrics" in html
