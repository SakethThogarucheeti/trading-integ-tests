"""Shared filesystem paths used across strategy integration tests."""

from __future__ import annotations

from pathlib import Path

# trading-platform/data/  (parents: [0]=utils [1]=testing [2]=strategy
#                                    [3]=trading-integ-tests [4]=trading (workspace root))
DATA_DIR = Path(__file__).parents[4] / "trading-platform" / "data"
