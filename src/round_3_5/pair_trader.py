import collections
from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order, Symbol

class Trader:
    def __init__(self):
        self.POSITION_LIMIT = 10
        self.price_history = collections.defaultdict(lambda: collections.deque(maxlen=20))
        
        # Pairs we found through correlation testing:
        # SNACKPACK_CHOCOLATE and SNACKPACK_VANILLA (-0.926)
        # MICROCHIP_OVAL and MICROCHIP_TRIANGLE (+0.870)
        # SLEEP_POD_COTTON and SLEEP_POD_POLYESTER (+0.875)
        # UV_VISOR_AMBER and UV_VISOR_MAGENTA (-0.867)
        # PEBBLES_S and PEBBLES_XL (-0.834)
        # ROBOT_MOPPING and ROBOT_IRONING (-0.815)
        
        self.pos_pairs = [
            ("MICROCHIP_OVAL", "MICROCHIP_TRIANGLE"),
            ("SLEEP_POD_COTTON", "SLEEP_POD_POLYESTER")
        ]
        
        self.neg_pairs = [
            ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA"),
            ("UV_VISOR_AMBER", "UV_VISOR_MAGENTA"),
            ("PEBBLES_S", "PEBBLES_XL"),
            ("ROBOT_MOPPING", "ROBOT_IRONING")
        ]

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
            if vwmp: self.price_history[product].append(vwmp)
            
        for a, b in self.pos_pairs:
            if a in state.order_depths and b in state.order_depths and len(self.price_history[a]) > 10:
                mean_a = sum(self.price_history[a]) / len(self.price_history[a])
                mean_b = sum(self.price_history[b]) / len(self.price_history[b])
                ratio = mean_a / mean_b if mean_b > 0 else 1
                curr_ratio = self.price_history[a][-1] / self.price_history[b][-1] if self.price_history[b][-1] > 0 else 1
                
                # If ratio is high, A is overvalued, B is undervalued
                if curr_ratio > ratio * 1.002:
                    self._sell_all(a, state, result)
                    self._buy_all(b, state, result)
                elif curr_ratio < ratio * 0.998:
                    self._buy_all(a, state, result)
                    self._sell_all(b, state, result)
                    
        for a, b in self.neg_pairs:
            if a in state.order_depths and b in state.order_depths and len(self.price_history[a]) > 10:
                # For negative pairs, when A goes up, B should go down
                # We calculate their relative positions from their own means
                mean_a = sum(self.price_history[a]) / len(self.price_history[a])
                mean_b = sum(self.price_history[b]) / len(self.price_history[b])
                
                pct_a = (self.price_history[a][-1] - mean_a) / mean_a
                pct_b = (self.price_history[b][-1] - mean_b) / mean_b
                
                # If they both moved the same direction (broken correlation)
                if pct_a > 0.001 and pct_b > 0.001:
                    self._sell_all(a, state, result)
                    self._sell_all(b, state, result)
                elif pct_a < -0.001 and pct_b < -0.001:
                    self._buy_all(a, state, result)
                    self._buy_all(b, state, result)

        return result, 0, ""
        
    def _buy_all(self, p, state, result):
        if p not in state.order_depths: return
        max_buy = self.POSITION_LIMIT - state.position.get(p, 0)
        best_ask = min(state.order_depths[p].sell_orders.keys()) if state.order_depths[p].sell_orders else None
        if max_buy > 0 and best_ask:
            result.setdefault(p, []).append(Order(p, best_ask, max_buy))
            
    def _sell_all(self, p, state, result):
        if p not in state.order_depths: return
        max_sell = -self.POSITION_LIMIT - state.position.get(p, 0)
        best_bid = max(state.order_depths[p].buy_orders.keys()) if state.order_depths[p].buy_orders else None
        if max_sell < 0 and best_bid:
            result.setdefault(p, []).append(Order(p, best_bid, max_sell))
