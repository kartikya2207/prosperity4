from datamodel import OrderDepth, TradingState, Order, Symbol
from typing import Dict, List
import collections

class Trader:
    def __init__(self):
        self.POSITION_LIMIT = 10
        self.price_history = collections.defaultdict(lambda: collections.deque(maxlen=20))
        self.inventory_risk_coeff = 0.5

    def get_vwmp(self, order_depth: OrderDepth):
        if not order_depth.buy_orders or not order_depth.sell_orders: return None
        best_bid, bid_vol = max(order_depth.buy_orders.items())
        best_ask, ask_vol = min(order_depth.sell_orders.items())
        ask_vol = abs(ask_vol) 
        if bid_vol + ask_vol == 0: return (best_bid + best_ask) / 2.0
        return (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

    def run(self, state: TradingState) -> tuple[Dict[Symbol, List[Order]], int, str]:
        result = {}
        for product, order_depth in state.order_depths.items():
            vwmp = self.get_vwmp(order_depth)
            if not vwmp: continue
            
            self.price_history[product].append(vwmp)
            
            # Use 20 periods
            if len(self.price_history[product]) < 10: 
                continue
                
            fast_ma = sum(self.price_history[product]) / len(self.price_history[product])
            current_pos = state.position.get(product, 0)
            max_buy = self.POSITION_LIMIT - current_pos
            max_sell = -self.POSITION_LIMIT - current_pos
            
            # Simple mean reversion
            orders = []
            
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            
            spread = best_ask - best_bid
            if spread == 1:
                pass
            
            limit_buy = int(fast_ma - 1.5 - current_pos * 0.5)
            limit_sell = int(fast_ma + 1.5 - current_pos * 0.5)

            if best_ask < fast_ma - 2 and max_buy > 0:
                orders.append(Order(product, best_ask, max_buy))
            elif limit_buy > 0 and max_buy > 0:
                buy_price = min(best_bid + 1, limit_buy)
                orders.append(Order(product, buy_price, max_buy))

            if best_bid > fast_ma + 2 and max_sell < 0:
                orders.append(Order(product, best_bid, max_sell))
            elif limit_sell > 0 and max_sell < 0:
                sell_price = max(best_ask - 1, limit_sell)
                orders.append(Order(product, sell_price, max_sell))

            if orders:
                result[product] = orders

        return result, 0, ""

