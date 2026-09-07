"""Pure balance and advisory-status rules for journal capital."""

from decimal import Decimal

from tradefog.domain.enums import StrategyStatus, WalletAssetStatus


def wallet_asset_status(
    balance: Decimal,
    risk_stop_capital: Decimal | None,
) -> WalletAssetStatus:
    """Derive deposit health without preventing discretionary trades."""
    if risk_stop_capital is not None and balance <= risk_stop_capital:
        return WalletAssetStatus.RISK_STOPPED
    return WalletAssetStatus.ACTIVE


def strategy_status(
    statuses: list[WalletAssetStatus],
) -> StrategyStatus:
    """Return the worst active allocation status for a strategy."""
    if WalletAssetStatus.RISK_STOPPED in statuses:
        return StrategyStatus.RISK_STOPPED
    if WalletAssetStatus.AT_RISK in statuses:
        return StrategyStatus.AT_RISK
    return StrategyStatus.ACTIVE
