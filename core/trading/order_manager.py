"""Order lifecycle manager: fill checks, validity, timeout, and expiry."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.trading.types import BarSignals, JudgmentConfig, Order, OrderEvent


@dataclass
class ManageResult:
    """Result of managing orders for one bar."""

    filled: list[OrderEvent] = field(default_factory=list)
    cancelled: list[OrderEvent] = field(default_factory=list)
    expired: list[OrderEvent] = field(default_factory=list)


class OrderManager:
    """Manage active limit orders through their lifecycle.

    Each bar:
      1. Check fills (bar touches order price)
      2. Check validity (prediction still covers order price + no reversal)
      3. Check timeout (waited too long)
    """

    def __init__(self, config: JudgmentConfig | None = None) -> None:
        self.config = config or JudgmentConfig()
        self.active_orders: list[Order] = []
        self._processed: dict[str, Order] = {}  # cache for recently processed orders

    def add_order(self, order: Order) -> None:
        self.active_orders.append(order)

    def manage(
        self,
        bar_high: float,
        bar_low: float,
        prediction: object | None = None,
        signals: BarSignals | None = None,
    ) -> ManageResult:
        """Process all active orders for one bar.

        Returns filled/cancelled/expired events.
        """
        result = ManageResult()
        remaining: list[Order] = []

        pred_low = getattr(prediction, "low", None)
        pred_high = getattr(prediction, "high", None)

        for order in self.active_orders:
            if order.status != "pending":
                continue

            # Fill check (limit order)
            if order.order_type == "limit" and order.price > 0:
                if bar_low <= order.price <= bar_high:
                    order.status = "filled"
                    result.filled.append(OrderEvent(
                        order_id=order.order_id,
                        action="filled",
                        price=order.price,
                    ))
                    continue
            elif order.order_type == "market":
                # Market orders fill immediately at current bar
                order.status = "filled"
                exec_price = (bar_high + bar_low) / 2
                result.filled.append(OrderEvent(
                    order_id=order.order_id,
                    action="filled",
                    price=exec_price,
                    reason="market",
                ))
                continue

            # Timeout check
            order.bars_waiting += 1
            if order.bars_waiting >= self.config.order_max_wait_bars:
                order.status = "expired"
                result.expired.append(OrderEvent(
                    order_id=order.order_id,
                    action="expired",
                    price=order.price,
                    reason=f"timeout:{order.bars_waiting}",
                ))
                continue

            # Validity check: signal reversal (independent of prediction)
            has_reversal = (
                signals is not None and (signals.exit or signals.reduce)
            )
            if has_reversal:
                order.status = "cancelled"
                result.cancelled.append(OrderEvent(
                    order_id=order.order_id,
                    action="cancelled",
                    price=order.price,
                    reason="signal_reversal",
                ))
                continue

            # Validity check: prediction coverage
            if pred_low is not None and pred_high is not None:
                price_in_range = pred_low <= order.price <= pred_high
                if not price_in_range:
                    order.status = "cancelled"
                    result.cancelled.append(OrderEvent(
                        order_id=order.order_id,
                        action="cancelled",
                        price=order.price,
                        reason="prediction_drift",
                    ))
                    continue

            remaining.append(order)

        # Cache processed orders for lookup (e.g., fill_order needs Order object)
        for o in self.active_orders:
            if o.status != "pending":
                self._processed[o.order_id] = o
        self._processed = {
            oid: o for oid, o in self._processed.items()
            if o.status != "pending"
        }

        self.active_orders = remaining
        return result

    def get_processed_order(self, order_id: str) -> Order | None:
        return self._processed.get(order_id)

    @property
    def has_pending_entry(self) -> bool:
        return any(o.source == "entry" and o.status == "pending" for o in self.active_orders)

    @property
    def pending_count(self) -> int:
        return len(self.active_orders)

    def clear(self) -> None:
        self.active_orders.clear()
        self._processed.clear()
