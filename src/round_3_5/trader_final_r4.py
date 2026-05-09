from datamodel import OrderDepth, UserId, TradingState, Order, Trade
from typing import List, Dict

POSITION_LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300, "VEV_5100": 300,
    "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300,
    "VEV_6000": 300, "VEV_6500": 300,
}

# STRATEGY:
# 1. PASSIVE MM on HP, VE, VEV_4000: bid+1/ask-1, proven ~1,400/day
# 2. SHORT VEV options: sell ONCE at the start to build a short position,
#    then HOLD. Do NOT churn. The theta decay and directional move give profit
#    at end-of-day liquidation against hidden fair value.
#    The key: don't keep placing sell orders every timestamp (causes churning).
#    Place sell ONCE when position is not yet at target.
#
# CRITICAL: The book has buy orders that match our sells. When we sell at bid+1,
# someone buys from us at bid+1. Then next timestamp, new buy orders appear.
# If we sell again, same thing. Each sell is at -1 edge (below mid).
# The churning kills us.
#
# FIX: Track position via state.position. Only place sell orders when position
# is far from target. Use traderData to track if we've already placed our shorts.
#
# Even simpler: use state.position to know our current position. Only sell
# if we haven't reached target yet. Don't place any buy orders for short targets.

VEV_STRIKES = {
    "VEV_4000": 4000, "VEV_4500": 4500, "VEV_5000": 5000, "VEV_5100": 5100,
    "VEV_5200": 5200, "VEV_5300": 5300, "VEV_5400": 5400, "VEV_5500": 5500,
    "VEV_6000": 6000, "VEV_6500": 6500,
}

# Products to short (sell at bid, hold to end for theta/directional profit)
SHORT_PRODUCTS = {
    "VEV_4500", "VEV_5000", "VEV_5100", "VEV_5200",
    "VEV_5300", "VEV_5400", "VEV_5500", "VEV_6000",
}

# Products for passive MM
MM_PRODUCTS = {"HYDROGEL_PACK", "VELVETFRUIT_EXTRACT", "VEV_4000"}

# Target short position for each VEV
SHORT_TARGET = -300  # max short


class Trader:

    def bid(self):
        return 15

    def _get_best(self, order_depth: OrderDepth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask

    def run(self, state: TradingState):
        result = {}

        for product in POSITION_LIMITS.keys():
            orders = []
            order_depth = state.order_depths.get(product)
            if not order_depth:
                continue

            pos = state.position.get(product, 0)
            limit = POSITION_LIMITS[product]
            best_bid, best_ask = self._get_best(order_depth)

            if best_bid is None or best_ask is None:
                result[product] = orders
                continue

            spread = best_ask - best_bid
            max_buy = limit - pos
            max_sell = limit + pos

            if product in MM_PRODUCTS:
                # === PASSIVE MM: bid+1/ask-1 ===
                if spread > 2:
                    buy_price = best_bid + 1
                    sell_price = best_ask - 1
                else:
                    buy_price = best_bid
                    sell_price = best_ask

                qty = 20 if product != "VELVETFRUIT_EXTRACT" else 15
                if max_buy > 0:
                    orders.append(Order(product, buy_price, min(qty, max_buy)))
                if max_sell > 0:
                    orders.append(Order(product, sell_price, -min(qty, max_sell)))
                # Backup at bid/ask
                orders.append(Order(product, best_bid, min(8, max_buy)))
                orders.append(Order(product, best_ask, -min(8, max_sell)))

            elif product in SHORT_PRODUCTS:
                # === SHORT VEV: sell ONCE to build position, then HOLD ===
                # Only sell if we haven't reached our target short position
                if pos > SHORT_TARGET:
                    # We need to sell more to reach target
                    sell_qty = min(pos - SHORT_TARGET, max_sell, 50)
                    if sell_qty > 0:
                        # Sell at best_ask to get filled fast
                        # (someone needs to buy from us)
                        orders.append(Order(product, best_ask, -sell_qty))
                        # Also try at ask-1 for better price
                        if spread > 1:
                            orders.append(Order(product, best_ask - 1, -min(sell_qty, 20)))
                # DO NOT place any buy orders - we want to stay short
                # DO NOT place sell orders if already at target - just hold

            elif product == "VEV_6500":
                # Too far OTM, skip
                pass

            # End of day flatten for MM products only
            if product in MM_PRODUCTS and state.timestamp > 950000:
                if pos > 0:
                    orders.append(Order(product, best_bid, -min(pos, max_sell)))
                elif pos < 0:
                    orders.append(Order(product, best_ask, min(-pos, max_buy)))

            result[product] = orders

        traderData = ""
        conversions = 0
        return result, conversions, traderData