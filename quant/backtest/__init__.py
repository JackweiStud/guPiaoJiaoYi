"""量化回测与绩效评估系统 (Backtesting Engine)"""

from quant.backtest.single_asset import (
    run_nextgen_single_backtest,
    compare_strategies_single_asset,
    calculate_metrics,
)

__all__ = [
    "run_nextgen_single_backtest",
    "compare_strategies_single_asset",
    "calculate_metrics",
]
