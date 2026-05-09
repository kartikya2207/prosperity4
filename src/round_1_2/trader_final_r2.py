import json
import math
import time
import statistics
import jsonpickle
from typing import Any, List, Dict, Tuple, Optional
from datamodel import (Listing, Observation, Order, OrderDepth,
                       ProsperityEncoder, Symbol, Trade, TradingState)


# ═════════════════════════════════════════════════════════════════════════════
# LOGGER
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
            self.compress_state(state,
                self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list:
        return [
            state.timestamp, trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings):
        return [[l.symbol, l.product, l.denomination]
                for l in listings.values()]

    def compress_order_depths(self, order_depths):
        return {s: [od.buy_orders, od.sell_orders]
                for s, od in order_depths.items()}

    def compress_trades(self, trades):
        out = []
        for arr in trades.values():
            for t in arr:
                out.append([t.symbol, t.price, t.quantity,
                             t.buyer, t.seller, t.timestamp])
        return out

    def compress_observations(self, obs):
        conv = {}
        for prod, o in obs.conversionObservations.items():
            conv[prod] = [o.bidPrice, o.askPrice, o.transportFees,
                          o.exportTariff, o.importTariff,
                          o.sugarPrice, o.sunlightIndex]
        return [obs.plainValueObservations, conv]

    def compress_orders(self, orders):
        return [[o.symbol, o.price, o.quantity]
                for arr in orders.values() for o in arr]

    def to_json(self, value):
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi, out = 0, min(len(value), max_length), ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate; lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


# ═════════════════════════════════════════════════════════════════════════════
# PERSISTENT STATE
# ═════════════════════════════════════════════════════════════════════════════
class State:
    def __init__(self):
        self.run_times_ms: List[float] = []

        # ACO: smoothed mid history for dynamic FV
        self.aco_mid_history: List[float] = []
        self.aco_long_history: List[float] = []   # FIX: dynamic anchor
        self.aco_fill_log: List[tuple] = []
        self.aco_clearing_log: List[int] = []

        # IPR: mid price history for slope/momentum
        self.ipr_mid_history: List[float] = []
        self.ipr_trend_slope: float = 0.0
        self.ipr_clearing_log: List[int] = []
        self.ipr_reversal_steps: int = 0          # FIX: track sustained reversal


# ═════════════════════════════════════════════════════════════════════════════
# TRADER
# ═════════════════════════════════════════════════════════════════════════════
class Trader:

    LIMITS = {
        "ASH_COATED_OSMIUM":    80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # ── ASH_COATED_OSMIUM params ──────────────────────────────────────────
    #
    # Market structure:
    #   Typical spread: ~16 ticks (bid ~9992, ask ~10010)
    #   FV: dynamic float from smoothed book mid, anchored to long-run mean
    #   Actual trade prices: 9988–10013 range
    #
    # Two-tier quoting:
    #   INNER (72 units): near FV — high fill probability, ~3-5 tick edge
    #   OUTER (8 units): penny-jump — captures extreme moves, ~8+ tick edge
    #
    # FIX: ACO_FAIR is now a fallback only. The real anchor is a 500-step
    # rolling mean of observed mids (self-correcting across days).
    #
    ACO_FAIR        = 10_000   # fallback anchor if long history is empty
    ACO_SPREAD      = 2        # fallback half-spread when book is thin
    ACO_MID_SMOOTH  = 8        # rolling window for short-run FV smoothing
    ACO_LONG_WIN    = 500      # rolling window for dynamic anchor
    ACO_MAX_SKEW    = 3        # max inventory-skew adjustment (ticks)
    ACO_FLATTEN_POS = 40       # |pos| above which we urgently unwind
    ACO_INNER_LOT   = 72       # units at inner (near-FV) quote tier
    ACO_OUTER_LOT   = 8        # units at outer (penny-jump) quote tier
    ACO_MIN_QUOTE   = 5        # FIX: don't post quotes smaller than this

    # ── INTARIAN_PEPPER_ROOT params ───────────────────────────────────────
    #
    # Market structure:
    #   Strong LINEAR uptrend: ~10,000 → ~13,000 over 3M timestamps
    #   OLS slope always ≥ 0.09 ticks/step (confirmed across all 3 days)
    #
    # Strategy: DIRECTIONAL LONG — hold max long, with exits on reversal.
    #
    # FIX: Added trend reversal exit. If OLS slope stays below
    # IPR_REVERSAL_THRESHOLD for IPR_REVERSAL_STEPS consecutive steps,
    # we unwind the position back to 0. This was the biggest risk in the
    # original code — being stuck at +80 if the trend changes.
    #
    # FIX: Passive bid is now clamped below best ask to prevent
    # accidentally crossing the spread when bid_boost pushes us too high.
    #
    # FIX: When pos > IPR_THROTTLE_POS, skip asks more than
    # IPR_THROTTLE_TICKS above mid to avoid chasing spiked ask prices.
    #
    IPR_TREND_WINDOW      = 50    # OLS slope calculation window
    IPR_BASE_OFFSET       = 1     # ticks above best bid for passive queue-jump
    IPR_SLOPE_BOOST_TH    = 0.08  # slope above which we boost bid by +1 tick
    IPR_REVERSAL_THRESHOLD = -0.05 # slope below which we consider trend reversed
    IPR_REVERSAL_STEPS    = 20    # how many consecutive steps before we unwind
    IPR_THROTTLE_POS      = 60    # |pos| above which we throttle aggressive buys
    IPR_THROTTLE_TICKS    = 3     # max ticks above mid we'll chase when throttled

    def __init__(self):
        self.logger = logger

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────
    def get_mid(self, od: OrderDepth) -> Optional[float]:
        if not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0

    def get_wall_mid(self, od: OrderDepth) -> Optional[float]:
        """Mid of highest-volume bid/ask — more stable than best bid/ask."""
        if not od.buy_orders or not od.sell_orders:
            return None
        wall_bid = max(od.buy_orders.items(),  key=lambda x: x[1])[0]
        wall_ask = min(od.sell_orders.items(), key=lambda x: abs(x[1]))[0]
        return (wall_bid + wall_ask) / 2.0

    def get_vwap_mid(self, od: OrderDepth) -> Optional[float]:
        """
        FIX: Volume-weighted average price mid.
        More robust than simple best-bid/ask mid — outlier single-lot
        quotes at extreme prices don't skew the FV estimate.
        """
        if not od.buy_orders or not od.sell_orders:
            return None
        bid_vol  = sum(od.buy_orders.values())
        ask_vol  = sum(abs(q) for q in od.sell_orders.values())
        if bid_vol == 0 or ask_vol == 0:
            return None
        bid_vwap = sum(p * q         for p, q in od.buy_orders.items()) / bid_vol
        ask_vwap = sum(p * abs(q)    for p, q in od.sell_orders.items()) / ask_vol
        return (bid_vwap + ask_vwap) / 2.0

    def compute_ols_slope(self, history: List[float], window: int) -> float:
        """OLS regression slope (ticks/step) over last `window` points."""
        n = min(len(history), window)
        if n < 3:
            return 0.0
        data  = history[-n:]
        x_bar = (n - 1) / 2.0
        y_bar = sum(data) / n
        num   = sum((i - x_bar) * (data[i] - y_bar) for i in range(n))
        den   = sum((i - x_bar) ** 2               for i in range(n))
        return num / den if den > 0 else 0.0

    def inventory_skew(self, pos: int, limit: int,
                       target: int = 0,
                       max_skew: int = 3) -> Tuple[int, int]:
        """
        Tilt quotes toward inventory reduction.
        Returns (bid_adj, ask_adj): both negative when long, positive when short.
        """
        ratio = (pos - target) / limit
        skew  = -int(round(ratio * max_skew))
        return skew, skew

    def compute_aco_fair_value(self, od: OrderDepth, ts: State) -> float:
        """
        FIX: Dynamic float FV with SELF-CORRECTING anchor.

        Previous version anchored 15% toward hardcoded 10,000 forever.
        If the true mean drifts across days (which it can), that anchor
        fights the market.

        Now: anchor is the 500-step rolling mean of observed mids.
        Starts at ACO_FAIR (fallback), self-corrects as data arrives.
        Short-run smoothing (8 steps) still filters tick noise.

        FLOAT return is critical for half-tick edge detection:
          FV=10000.5, ask=10000 → 10000 < 10000.5 → take it.
          Integer FV → miss.
        """
        # Prefer VWAP mid > wall mid > best mid
        mid = self.get_vwap_mid(od) or self.get_wall_mid(od) or self.get_mid(od)
        if mid is None:
            return float(self.ACO_FAIR)

        # Short-run smoother (fast, 8 steps)
        ts.aco_mid_history.append(mid)
        if len(ts.aco_mid_history) > self.ACO_MID_SMOOTH:
            ts.aco_mid_history.pop(0)
        smoothed = statistics.mean(ts.aco_mid_history)

        # FIX: Long-run anchor (slow, 500 steps) — replaces hardcoded 10,000
        ts.aco_long_history.append(mid)
        if len(ts.aco_long_history) > self.ACO_LONG_WIN:
            ts.aco_long_history.pop(0)
        anchor = statistics.mean(ts.aco_long_history) if ts.aco_long_history else float(self.ACO_FAIR)

        return 0.85 * smoothed + 0.15 * anchor

    # ─────────────────────────────────────────────────────────────────────
    # FILL LOGGER
    # ─────────────────────────────────────────────────────────────────────
    def log_fills(self, state: TradingState, ts: State) -> None:
        for product, trades in state.own_trades.items():
            for t in trades:
                side = "BUY" if t.buyer == "SUBMISSION" else "SELL"
                if product == "ASH_COATED_OSMIUM":
                    edge = t.price - self.ACO_FAIR
                    self.logger.print(
                        f"[FILL] ACO  {side} {abs(t.quantity)}x@{t.price}"
                        f"  edge={edge:+.1f}"
                    )
                    ts.aco_fill_log.append(
                        (state.timestamp, side, t.price, edge))
                    if len(ts.aco_fill_log) > 200:
                        ts.aco_fill_log.pop(0)
                    ts.aco_clearing_log.append(t.price)
                    if len(ts.aco_clearing_log) > 200:
                        ts.aco_clearing_log.pop(0)
                elif product == "INTARIAN_PEPPER_ROOT":
                    self.logger.print(
                        f"[FILL] IPR  {side} {abs(t.quantity)}x@{t.price}"
                    )
                    ts.ipr_clearing_log.append(t.price)
                    if len(ts.ipr_clearing_log) > 200:
                        ts.ipr_clearing_log.pop(0)

    # ─────────────────────────────────────────────────────────────────────
    # MAIN RUN
    # ─────────────────────────────────────────────────────────────────────
    def run(self, state: TradingState
            ) -> Tuple[Dict[str, List[Order]], int, str]:
        t_start = time.perf_counter()

        if state.traderData:
            try:
                ts = jsonpickle.decode(state.traderData)
                if type(ts) is dict:
                    ts = State()
                else:
                    # Forward-compatibility: add any new attrs with defaults
                    for attr, default in [
                        ("aco_mid_history",   []),
                        ("aco_long_history",  []),    # FIX: new
                        ("aco_fill_log",      []),
                        ("aco_clearing_log",  []),
                        ("ipr_mid_history",   []),
                        ("ipr_trend_slope",   0.0),
                        ("ipr_clearing_log",  []),
                        ("ipr_reversal_steps", 0),    # FIX: new
                        ("run_times_ms",      []),
                    ]:
                        if not hasattr(ts, attr):
                            setattr(ts, attr, default)
            except Exception:
                ts = State()
        else:
            ts = State()

        self.log_fills(state, ts)

        result: Dict[str, List[Order]] = {}
        conversions = 0

        for product in state.order_depths:
            if product == "ASH_COATED_OSMIUM":
                result[product] = self.trade_ash_coated_osmium(
                    state, product, ts)
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self.trade_pepper_root(
                    state, product, ts)

        trader_data = jsonpickle.encode(ts)

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        ts.run_times_ms.append(elapsed_ms)
        if len(ts.run_times_ms) > 50:
            ts.run_times_ms.pop(0)
        avg_ms = statistics.mean(ts.run_times_ms)
        if elapsed_ms > 200:
            self.logger.print(f"[PERF] ⚠️ {elapsed_ms:.1f}ms  avg={avg_ms:.1f}ms")
        elif state.timestamp % 10000 == 0:
            self.logger.print(f"[PERF] ✓ avg={avg_ms:.1f}ms")

        self.logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    # ═════════════════════════════════════════════════════════════════════
    # ASH-COATED OSMIUM — wide-spread stationary mean-reversion MM
    #
    # Typical book: bid ~9992, ask ~10010 (spread ≈ 16 ticks), FV ≈ 10001.
    #
    # OPT 1 — Aggressive take: any ask < FV_float or bid > FV_float.
    #          FLOAT comparison catches half-tick edges.
    #
    # OPT 3 — Position-reduce at FV boundary + urgent flatten when deep.
    #
    # OPT 2 — Two-tier passive quoting with inventory skew:
    #   INNER (72 units): inside spread, near FV. High fill probability.
    #   OUTER (8 units): penny-jump competing MM. Captures extreme moves.
    #
    # FIX: VWAP mid used for FV (more robust than best bid/ask mid).
    # FIX: Dynamic anchor replaces hardcoded 10,000.
    # FIX: Min quote size guard — don't post useless tiny quotes.
    # ═════════════════════════════════════════════════════════════════════
    def trade_ash_coated_osmium(self, state: TradingState, product: str,
                                ts: State) -> List[Order]:
        orders: List[Order] = []
        pos    = state.position.get(product, 0)
        limit  = self.LIMITS[product]
        od     = state.order_depths[product]

        # ── Dynamic float FV ─────────────────────────────────────────────
        FV_float = self.compute_aco_fair_value(od, ts)
        FV_low   = int(math.floor(FV_float))
        FV_high  = int(math.ceil(FV_float))
        if FV_low == FV_high:
            FV_high = FV_low + 1

        bid_adj, ask_adj = self.inventory_skew(pos, limit, 0, self.ACO_MAX_SKEW)
        buy_cap  = max(0, limit - pos)
        sell_cap = max(0, limit + pos)

        self.logger.print(
            f"[ACO] FV={FV_float:.2f} [{FV_low}/{FV_high}]  "
            f"pos={pos}  skew=({bid_adj},{ask_adj})"
        )

        # ── OPT 1: Aggressive take on mispriced levels ───────────────────
        for ask_px in sorted(od.sell_orders.keys()):
            if ask_px >= FV_float or buy_cap <= 0:
                break
            qty = min(abs(od.sell_orders[ask_px]), buy_cap)
            orders.append(Order(product, ask_px, qty))
            buy_cap -= qty
            self.logger.print(f"[ACO OPT1] TAKE-BUY  {qty}x@{ask_px}")

        for bid_px in sorted(od.buy_orders.keys(), reverse=True):
            if bid_px <= FV_float or sell_cap <= 0:
                break
            qty = min(od.buy_orders[bid_px], sell_cap)
            orders.append(Order(product, bid_px, -qty))
            sell_cap -= qty
            self.logger.print(f"[ACO OPT1] TAKE-SELL {qty}x@{bid_px}")

        # ── OPT 3: Position-reduce at FV boundary ────────────────────────
        if FV_low in od.sell_orders and pos < 0 and buy_cap > 0:
            qty = min(abs(od.sell_orders[FV_low]), buy_cap, abs(pos))
            if qty > 0:
                orders.append(Order(product, FV_low, qty))
                buy_cap -= qty

        if FV_high in od.buy_orders and pos > 0 and sell_cap > 0:
            qty = min(od.buy_orders[FV_high], sell_cap, pos)
            if qty > 0:
                orders.append(Order(product, FV_high, -qty))
                sell_cap -= qty

        # Extended OPT 3: urgently flatten when deeply off-side
        if pos < -self.ACO_FLATTEN_POS and buy_cap > 0:
            take_px = FV_low + 1
            if take_px in od.sell_orders:
                qty = min(abs(od.sell_orders[take_px]), buy_cap)
                if qty > 0:
                    orders.append(Order(product, take_px, qty))
                    buy_cap -= qty

        if pos > self.ACO_FLATTEN_POS and sell_cap > 0:
            take_px = FV_high - 1
            if take_px in od.buy_orders:
                qty = min(od.buy_orders[take_px], sell_cap)
                if qty > 0:
                    orders.append(Order(product, take_px, -qty))
                    sell_cap -= qty

        # ── OPT 2: Two-tier passive quoting ──────────────────────────────
        competing_asks = [px for px in od.sell_orders if px >= FV_high]
        competing_bids = [px for px in od.buy_orders  if px <= FV_low]

        outer_bid_raw = (max(competing_bids) + 1) if competing_bids else (FV_low  - self.ACO_SPREAD)
        outer_ask_raw = (min(competing_asks) - 1) if competing_asks else (FV_high + self.ACO_SPREAD)

        outer_bid = min(int(outer_bid_raw) + bid_adj, FV_low)
        outer_ask = max(int(outer_ask_raw) + ask_adj, FV_high)

        inner_bid = min(FV_low - 1 + bid_adj, FV_low)
        inner_ask = max(FV_high + 1 + ask_adj, FV_high)

        # FIX: Only post quotes if we have meaningful capacity (avoid tiny
        # rounding-error orders that waste slots and look weak to the book)
        if buy_cap >= self.ACO_MIN_QUOTE:
            inner_qty = min(self.ACO_INNER_LOT, buy_cap)
            orders.append(Order(product, inner_bid, inner_qty))
            buy_cap -= inner_qty
            if buy_cap >= self.ACO_MIN_QUOTE and outer_bid < inner_bid:
                outer_qty = min(self.ACO_OUTER_LOT, buy_cap)
                if outer_qty > 0:
                    orders.append(Order(product, outer_bid, outer_qty))

        if sell_cap >= self.ACO_MIN_QUOTE:
            inner_qty = min(self.ACO_INNER_LOT, sell_cap)
            orders.append(Order(product, inner_ask, -inner_qty))
            sell_cap -= inner_qty
            if sell_cap >= self.ACO_MIN_QUOTE and outer_ask > inner_ask:
                outer_qty = min(self.ACO_OUTER_LOT, sell_cap)
                if outer_qty > 0:
                    orders.append(Order(product, outer_ask, -outer_qty))

        self.logger.print(
            f"[ACO OPT2] inner_bid={inner_bid}  inner_ask={inner_ask}  "
            f"outer_bid={outer_bid}  outer_ask={outer_ask}  "
            f"buy_cap={buy_cap}  sell_cap={sell_cap}"
        )
        return orders

    # ═════════════════════════════════════════════════════════════════════
    # INTARIAN PEPPER ROOT — directional long on strong linear uptrend
    #
    # OPT A — Take asks aggressively.
    #   FIX: When pos > IPR_THROTTLE_POS, skip asks more than
    #   IPR_THROTTLE_TICKS above mid — avoids chasing price spikes when
    #   already deeply long.
    #
    # OPT B — Passive overbid for remaining capacity.
    #   FIX: Clamped to stay strictly below best ask — prevents accidental
    #   spread crossing when bid_boost pushes bid too high.
    #
    # OPT C — No passive asks (intentional: don't forfeit drift alpha).
    #
    # FIX (BIGGEST): Trend reversal exit.
    #   Track consecutive steps where slope < IPR_REVERSAL_THRESHOLD.
    #   After IPR_REVERSAL_STEPS sustained steps, unwind position to 0.
    #   This protects against being stuck at +80 in a trend change.
    # ═════════════════════════════════════════════════════════════════════
    def trade_pepper_root(self, state: TradingState, product: str,
                          ts: State) -> List[Order]:
        orders: List[Order] = []
        od    = state.order_depths[product]
        pos   = state.position.get(product, 0)
        limit = self.LIMITS[product]

        buy_cap  = max(0, limit - pos)
        sell_cap = max(0, pos)   # FIX: for reversal unwind

        # ── Update mid history and compute trend slope ─────────────────
        # FIX: prefer VWAP mid for slope calculation too
        mid = self.get_vwap_mid(od) or self.get_wall_mid(od) or self.get_mid(od)
        if mid is not None:
            ts.ipr_mid_history.append(mid)
            if len(ts.ipr_mid_history) > 300:
                ts.ipr_mid_history.pop(0)

        slope = self.compute_ols_slope(ts.ipr_mid_history, self.IPR_TREND_WINDOW)
        ts.ipr_trend_slope = slope

        # ── FIX: Trend reversal detection ────────────────────────────────
        # Count consecutive steps where slope is clearly negative.
        # After IPR_REVERSAL_STEPS sustained steps, begin unwinding.
        if slope < self.IPR_REVERSAL_THRESHOLD:
            ts.ipr_reversal_steps += 1
        else:
            ts.ipr_reversal_steps = 0   # reset counter on any non-reversal step

        in_reversal = ts.ipr_reversal_steps >= self.IPR_REVERSAL_STEPS

        self.logger.print(
            f"[IPR] pos={pos}  mid={mid}  slope={slope:.4f}  "
            f"buy_cap={buy_cap}  rev_steps={ts.ipr_reversal_steps}"
            f"{'  ⚠️ REVERSING' if in_reversal else ''}"
        )

        # ── REVERSAL MODE: Unwind position ───────────────────────────────
        if in_reversal and pos > 0:
            self.logger.print(f"[IPR REVERSAL] Unwinding {pos} units")
            for bid_px in sorted(od.buy_orders.keys(), reverse=True):
                if sell_cap <= 0:
                    break
                qty = min(od.buy_orders[bid_px], sell_cap)
                orders.append(Order(product, bid_px, -qty))
                sell_cap -= qty
                self.logger.print(f"[IPR REV] TAKE-SELL {qty}x@{bid_px}")
            # Don't buy during reversal
            return orders

        # ── OPT A: Take asks — with throttle when nearly full ────────────
        for ask_px in sorted(od.sell_orders.keys()):
            if buy_cap <= 0:
                break
            # FIX: When deeply long, skip asks that are too far above mid
            # — avoids paying a spike premium when already well-positioned.
            if pos > self.IPR_THROTTLE_POS and mid is not None:
                if ask_px > mid + self.IPR_THROTTLE_TICKS:
                    self.logger.print(
                        f"[IPR OPT A] SKIP-SPIKE {ask_px} > mid+{self.IPR_THROTTLE_TICKS}")
                    continue
            qty = min(abs(od.sell_orders[ask_px]), buy_cap)
            orders.append(Order(product, ask_px, qty))
            buy_cap -= qty
            self.logger.print(f"[IPR OPT A] TAKE-BUY {qty}x@{ask_px}")

        # ── OPT B: Passive overbid for remaining capacity ─────────────────
        if buy_cap > 0:
            bid_boost = self.IPR_BASE_OFFSET + (1 if slope >= self.IPR_SLOPE_BOOST_TH else 0)

            if od.buy_orders:
                best_bid = max(od.buy_orders.keys())
                our_bid  = best_bid + bid_boost
            elif mid is not None:
                our_bid = int(mid) - 1
            else:
                our_bid = None

            # FIX: Clamp below best ask — never accidentally cross the spread
            if our_bid is not None and od.sell_orders:
                best_ask = min(od.sell_orders.keys())
                our_bid  = min(our_bid, best_ask - 1)

            if our_bid is not None:
                orders.append(Order(product, int(our_bid), buy_cap))
                self.logger.print(
                    f"[IPR OPT B] PASSIVE-BID {buy_cap}x@{our_bid}  "
                    f"boost={bid_boost}"
                )

        # ── OPT C: No passive asks (intentionally omitted) ───────────────
        return orders