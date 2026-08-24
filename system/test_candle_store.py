"""
CandleStore + CandleDataStore integration tests (Postgres round-trip).

Migrated from trading-platform/tst/unit/indicators/test_store.py -- unit
suites shouldn't spin up a Postgres container (that's what this repo's
system/ package is for). Row counts are kept to the minimum each assertion
actually needs (see individual test comments) rather than the larger
fixture data the original carried, per this repo's convention of using as
little data as possible to keep the Docker-backed suite fast.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading.candles.storage.store import CandleDataStore
from trading.storage.stores.candle_store import CandleStore


async def test_save_and_get_candles(engine, session_factory) -> None:
    candle_store = CandleDataStore(session_factory)

    rows = [
        {
            "symbol": "INFY",
            "interval": "15min",
            "ts": datetime(2024, 1, 2, 9, 15, tzinfo=UTC),
            "open": 1500.0,
            "high": 1510.0,
            "low": 1495.0,
            "close": 1505.0,
            "volume": 10000,
        },
        {
            "symbol": "INFY",
            "interval": "15min",
            "ts": datetime(2024, 1, 2, 9, 30, tzinfo=UTC),
            "open": 1505.0,
            "high": 1520.0,
            "low": 1500.0,
            "close": 1515.0,
            "volume": 12000,
        },
    ]
    await candle_store.save_candles(rows)
    result = await candle_store.get_candles("INFY", "15min", limit=10)

    assert len(result) == 2
    assert result[0]["close"] == pytest.approx(1505.0)
    assert result[1]["close"] == pytest.approx(1515.0)
    assert result[0]["ts"] < result[1]["ts"]


async def test_save_candles_idempotent(engine, session_factory) -> None:
    candle_store = CandleDataStore(session_factory)

    row = {
        "symbol": "TCS",
        "interval": "1min",
        "ts": datetime(2024, 1, 3, 9, 15, tzinfo=UTC),
        "open": 3000.0,
        "high": 3010.0,
        "low": 2995.0,
        "close": 3005.0,
        "volume": 5000,
    }

    await candle_store.save_candles([row])
    await candle_store.save_candles([row])

    result = await candle_store.get_candles("TCS", "1min", limit=10)
    assert len(result) == 1


async def test_get_candles_since(engine, session_factory) -> None:
    candle_store = CandleDataStore(session_factory)

    # 4 rows is the minimum that proves the "since" filter actually filters:
    # 2 before the cutoff (excluded), 2 at/after it (included).
    base = datetime(2024, 1, 4, 9, 0, tzinfo=UTC)
    rows = [
        {
            "symbol": "RELIANCE",
            "interval": "15min",
            "ts": base + timedelta(minutes=15 * i),
            "open": 2000.0,
            "high": 2010.0,
            "low": 1995.0,
            "close": 2005.0,
            "volume": 8000,
        }
        for i in range(4)
    ]
    await candle_store.save_candles(rows)

    since = base + timedelta(minutes=15 * 2)
    result = await candle_store.get_candles_since("RELIANCE", "15min", since)

    assert len(result) == 2


async def test_candle_store_end_to_end(engine, session_factory) -> None:
    from quantindicators.library.ema import EMA

    candle_store = CandleDataStore(session_factory)

    # EMA(period=9) returns None below `period` bars available (see
    # quantindicators' EMA.compute) -- 9 is the minimum that exercises the
    # real CandleStore -> EMA wiring instead of hitting that None branch.
    base = datetime(2024, 1, 5, 9, 15, tzinfo=UTC)
    rows = [
        {
            "symbol": "HDFC",
            "interval": "15min",
            "ts": base + timedelta(minutes=15 * i),
            "open": 200.0,
            "high": 201.0,
            "low": 199.0,
            "close": 200.0,
            "volume": 1000,
        }
        for i in range(9)
    ]
    await candle_store.save_candles(rows)

    store = CandleStore(candle_store=candle_store)
    ema = EMA(store, "HDFC", "15min")
    result = await ema.compute(EMA.Parameters(period=9))
    assert result == pytest.approx(200.0, rel=1e-3)
