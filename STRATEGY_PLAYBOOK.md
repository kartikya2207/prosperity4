# From Insight to Strategy — The Translation Playbook

This doc turns every piece of data insight into a specific code-level decision you can make inside `trader.py`. Read alongside the notebook.

---

## Step 1 — Read the Thesis Dashboard at the bottom of the notebook

After running all lenses, the final cell prints a summary card per product. Five numbers drive every strategy decision:

1. **Mid price mean & std** → where does it live, how wide is the range
2. **Returns σ (volatility)** → how much it moves tick-to-tick
3. **Median spread** → what the market is charging per round-trip
4. **Spread / σ ratio** → is market-making viable at all
5. **Lag autocorrelations** → is there real time-series structure

---

## Step 2 — Map the fingerprints to archetype

Use this table. Find the row that matches your data; the strategy column is your plan.

| Lens fingerprint | Archetype | Strategy |
|---|---|---|
| Flat price, σ << spread, lags ≈ 0 | Stationary random walk | **Market-make around fixed fair** |
| Linear drift, σ << spread, lags ≈ 0 | Deterministic trend | **Market-make around moving fair (wall_mid or fitted trend)** |
| Sawtooth on a slope, real lag-2/5 < 0 | Trend + reversion | **Above + reversion overlay when far from trend** |
| Bell price, σ ≈ spread, lags ≈ 0 | Marginal market | **Thin quotes, rely on volume, tight risk** |
| Bell but lag 1..5 strongly negative | True mean reversion | **Threshold-trade the z-score** |
| Bell but lag 1..5 positive | True momentum | **Ride the direction with trailing exit** |
| Jumpy (high excess kurt) | Jump risk | **Reduce size; add pull-quotes-on-event rule** |
| Flow 70/30 toward one side | One-sided pressure | **Shift fair toward the aggressive side** |
| Dominant quantity at daily extremes | Olivia-style bot | **Detect and piggyback** |
| Basket = linear combo of constituents | Arbitrage | **Spread-trade synthetic vs market** |
| Price = f(underlying, vol, time) | Option | **Fit implied vol; trade deviations** |

---

## Step 3 — Parameterize from your data

For each product, extract these specific numbers from the notebook and plug them into your trader. **Do not hardcode round numbers from memory — read them from your data.**

```python
PARAMS = {
    "INTARIAN_PEPPER_ROOT": {
        "fair_type": "wall_mid",       # tracks the trend automatically
        "returns_sigma": 3.3,          # from returns table
        "spread_median": 14,           # from viability table
        "take_edge": 1,
        "make_edge": 1,
        "position_limit": 80,
        "max_quote_size": 20,
    },
    "ASH_COATED_OSMIUM": {
        "fair_type": "wall_mid",
        "fair_fixed_fallback": 10000,
        "returns_sigma": 3.7,
        "spread_median": 16,
        "take_edge": 1,
        "make_edge": 1,
        "position_limit": 80,
        "max_quote_size": 20,
    },
}
```

---

## Step 4 — Know which function to edit for which change

| What I want to change | File location |
|---|---|
| Take thresholds, make offsets | `market_make()` helper |
| How fair value is estimated | `wall_mid()` or new `estimate_fair_<product>()` function |
| Product-specific logic | `trade_<product>()` function |
| Add a new product | Add to `PARAMS`, add a `trade_<product>()`, add `elif` in `Trader.run()` |
| Parameters (edges, sizes) | `PARAMS` dict at the top |
| Memory across ticks | `self.state` attributes OR encode into `trader_data` JSON |

---

## Step 5 — The iteration discipline

After every change, run the backtester and answer:

1. Did total PnL go up or down?
2. Which product changed, in the direction I expected?
3. Robust across all days, or driven by one lucky day?
4. What were max drawdown and max position?

If a change helped ONE day but hurt another, it's overfitting — reject. Flat-good beats peak-great.

Keep a plain-text log: `v1: +12k | v2: +14k added wall_mid | v3: -2k widened edge too far`. Future-you will thank present-you.

---

## Step 6 — When to move on

Plateau signals:
- PnL positive and stable across all days
- Small parameter changes shift PnL < 5%
- You can state your edge in one sentence

When that happens, leave the product and work on the next. Chasing the last 2% on a solved product costs time you need for unsolved ones.

---

## Step 7 — Position management

Every strategy dies on position limits. Rules:

- **Asymmetric quoting.** If long 60/80: quote buy smaller (5), sell normal (20). Bleeds inventory toward flat.
- **Flatten-at-fair.** When |position| > 50% limit, add small market order toward zero *when near fair*. Never flatten in loss.
- **Hard stop.** If at limit, stop new orders on that side.

---

## Step 8 — Fail safes

- **Position check before EVERY order.** One over limit and ALL orders rejected.
- **Integer prices/quantities only.**
- **Stdlib-only in submitted file.** No numpy, no pandas.
- **Fast per tick.** Avoid O(n²) over history.
- **`trader_data` has a size limit.** Keep state compact.
