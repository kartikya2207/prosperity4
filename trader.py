import json
import math
import statistics
from collections import deque
from typing import Any, List, Dict, Tuple, Optional
from datamodel import (Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState)

# ═════════════════════════════════════════════════════════════════════════════
# LOGGER (Stdlib Only)
# ═════════════════════════════════════════════════════════════════════════════
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict, conversions: int,
              trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions, "", "",
        ]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list:
        return [
            state.timestamp, trader_data,
            [[l.symbol, l.product, l.denomination] for l in state.listings.values()],
            {s: [od.buy_orders, od.sell_orders] for s, od in state.order_depths.items()},
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for arr in state.own_trades.values() for t in arr],
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
             for arr in state.market_trades.values() for t in arr],
            state.position,
            [state.observations.plainValueObservations, 
             {p: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
              for p, o in state.observations.conversionObservations.items()}]
        ]

    def compress_orders(self, orders):
        return [[o.symbol, o.price, o.quantity]
                for arr in orders.values() for o in arr]

    def to_json(self, value):
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if not value: return ""
        if len(json.dumps(value)) <= max_length: return value
        return value[:max_length//2] + "..."

logger = Logger()

# ═════════════════════════════════════════════════════════════════════════════
# TRADER
# ═════════════════════════════════════════════════════════════════════════════
class Trader:
    LIMITS = {
        "ASH_COATED_OSMIUM":    80,
        "INTARIAN_PEPPER_ROOT": 80,
        "HYDROGEL_PACK":        200,
        "VELVETFRUIT_EXTRACT":  200,
        "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300, "VEV_5100": 300,
        "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300,
        "VEV_6000": 300, "VEV_6500": 300,
    }

    def __init__(self):
        self.ema_mids = {}
        self.ema_alpha = 0.1
        self.ipr_history: deque = deque(maxlen=50)
        
    def get_mid(self, od: OrderDepth) -> Optional[float]:
        if not od.buy_orders or not od.sell_orders: return None
        return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0

    def compute_ols_slope(self, history: List[float], window: int = 50) -> float:
        n = min(len(history), window)
        if n < 3: return 0.0
        data = history[-n:]
        x_bar = (n - 1) / 2.0
        y_bar = sum(data) / n
        num = sum((i - x_bar) * (data[i] - y_bar) for i in range(n))
        den = sum((i - x_bar) ** 2 for i in range(n))
        return num / den if den > 0 else 0.0

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result = {}
        conversions = 0
        
        # 1. Update EMAs for all products
        for product, od in state.order_depths.items():
            mid = self.get_mid(od)
            if mid is not None:
                self.ema_mids[product] = self.ema_alpha * mid + (1 - self.ema_alpha) * self.ema_mids.get(product, mid)

        # 2. Strategy Implementation
        for product in state.order_depths:
            orders = []
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            limit = self.LIMITS.get(product, 20)
            best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
            best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
            
            if best_bid is None or best_ask is None: continue

            # --- ASH_COATED_OSMIUM (Mean Reversion) ---
            if product == "ASH_COATED_OSMIUM":
                fair = self.ema_mids.get(product, 10000)
                if best_ask < fair - 1:
                    orders.append(Order(product, best_ask, limit - pos))
                elif best_bid > fair + 1:
                    orders.append(Order(product, best_bid, -limit - pos))
                # Passive MM
                buy_qty = max(0, limit - pos - 20)
                sell_qty = max(0, limit + pos - 20)
                if buy_qty > 0:
                    orders.append(Order(product, int(fair-2), buy_qty))
                if sell_qty > 0:
                    orders.append(Order(product, int(fair+2), -sell_qty))

            # --- INTARIAN_PEPPER_ROOT (Trend Following) ---
            elif product == "INTARIAN_PEPPER_ROOT":
                mid = self.get_mid(od)
                self.ipr_history.append(mid)
                slope = self.compute_ols_slope(list(self.ipr_history))
                if slope > 0.05:
                    orders.append(Order(product, best_ask, limit - pos))
                elif slope < -0.05:
                    orders.append(Order(product, best_bid, -(limit + pos)))

            # --- HYDROGEL_PACK & VELVETFRUIT_EXTRACT (Passive MM) ---
            elif product in ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT", "VEV_4000"]:
                fair = self.ema_mids.get(product, mid)
                orders.append(Order(product, best_bid + 1 if best_ask-best_bid > 2 else best_bid, min(20, limit - pos)))
                orders.append(Order(product, best_ask - 1 if best_ask-best_bid > 2 else best_ask, -min(20, limit + pos)))

            # --- VEV VOUCHERS (Volatility / Theta Short) ---
            elif product.startswith("VEV_") and product != "VEV_4000":
                short_target = -300
                if pos > short_target:
                    orders.append(Order(product, best_bid, -min(pos - short_target, 50)))

            if orders:
                result[product] = orders

        # End of day flatten — hit current best bid/ask to guarantee fill
        if state.timestamp > 995000:
            for product, pos in state.position.items():
                od = state.order_depths.get(product)
                if pos > 0 and od and od.buy_orders:
                    result.setdefault(product, []).append(Order(product, max(od.buy_orders.keys()), -pos))
                elif pos < 0 and od and od.sell_orders:
                    result.setdefault(product, []).append(Order(product, min(od.sell_orders.keys()), -pos))

        logger.flush(state, result, conversions, "")
        return result, conversions, ""
