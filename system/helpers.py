"""Shared test helpers for system tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from trading.core.clock import Clock
from trading.core.schemas import SignalEvent, SignalType, ValidatedOrderEvent
from trading.execution.storage.store import PositionStore, TradingStore
from trading.risk.service.filter import RiskConfig, RiskFilter
from trading.storage.cache import setup_cache
from trading.tick_ingest.service.ingestor import CircuitBreaker
from trading.tick_ingest.storage.store import AuditStore
from trading_risk_sdk.gates.circuit_breaker import CircuitBreakerGate
from trading_risk_sdk.gates.daily_loss import DailyLossGate
from trading_risk_sdk.gates.duplicate_position import DuplicatePositionGate
from trading_risk_sdk.gates.time_cutoff import TimeCutoffGate


def make_risk_filter(
    session_factory: async_sessionmaker,
    *,
    config: RiskConfig | None = None,
    clock: Clock | None = None,
    circuit: CircuitBreaker | None = None,
) -> RiskFilter:
    """
    RiskFilter with the standard 4-gate stack used across system tests.

    DailyLossGate is disabled by default (paper mode: skip daily loss check).
    Pass `config` to override RiskConfig fields (e.g. cutoff/equity), or
    `circuit` for a pre-opened CircuitBreaker (e.g. to test the open-circuit
    rejection path).
    """
    setup_cache(None)
    trading = TradingStore(session_factory)
    audit = AuditStore(session_factory)
    position = PositionStore(session_factory)
    return RiskFilter(
        config=config
        or RiskConfig(equity=1_000_000.0, intraday_cutoff_hour=15, intraday_cutoff_minute=30),
        gates=[
            TimeCutoffGate(),
            CircuitBreakerGate(),
            DailyLossGate(enabled=False),
            DuplicatePositionGate(),
        ],
        trading=trading,
        audit=audit,
        position=position,
        clock=clock,
        circuit=circuit if circuit is not None else CircuitBreaker(),
    )


async def seed_signal(session_factory: async_sessionmaker, event: ValidatedOrderEvent) -> None:
    """
    Insert a Signal row for a ValidatedOrderEvent's signal_id.

    OrderExecutor has a FK constraint: orders.signal_id → signals.id.
    In the live pipeline RiskFilter inserts this row before returning the
    ValidatedOrderEvent. Tests that call OrderExecutor directly must call this first.
    """
    sig = SignalEvent(
        signal_id=event.signal_id,
        symbol=event.symbol,
        instrument_type=event.instrument_type,
        side=event.side,
        strategy_id="test",
        signal_type=SignalType.ENTRY,
        stop_distance=1.0,
        tick_log_id=0,
    )
    store = TradingStore(session_factory)
    await store.save_signal(sig)
