"""
Counterparty flow classifier.
================================================================================

Round 4 is the one round whose trade logs reveal counterparty IDs (the "Mark NN"
bots). This module builds a per-counterparty ledger from the REAL round-4 trade
data and classifies each counterparty as "informed" (the market tends to move in
their favor after they trade) vs "noise" (it moves against them).

For every trade we take BOTH sides' perspective:
  * the buyer is long at the trade price; favorable = mid rises afterwards
  * the seller is short at the trade price; favorable = mid falls afterwards

Per counterparty we compute:
  * n_trades, total quantity, and signed (net) volume
  * avg edge vs mid  -- signed so that + = they crossed the spread / paid up
                        (took liquidity aggressively), - = they were passive
  * forward return   -- quantity-weighted, signed by their side, in basis points,
                        measured H ticks after each trade (within the same day)
  * win rate         -- fraction of trades where the forward move went their way

Classification: informed if mean signed forward return > 0, else noise.

Run from the repo root:

    python src/analysis/counterparty.py

Outputs a ranked table and plots/counterparty_classification.png.

NOTE: round 5's trade logs do NOT contain counterparty IDs (buyer/seller are
blank), so this analysis is necessarily built on the round-4 data.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DAYS = [
    (
        os.path.join(REPO, "data", "round4", f"trades_round_4_day_{d}.csv"),
        os.path.join(REPO, "data", "round4", f"prices_round_4_day_{d}.csv"),
    )
    for d in (1, 2, 3)
]
FORWARD_TICKS = 5000  # horizon over which "did it move their way?" is measured


def build_ledger():
    """Return a per-(trade, side) DataFrame with forward returns attached."""
    rows = []
    for tfile, pfile in DAYS:
        if not (os.path.exists(tfile) and os.path.exists(pfile)):
            print(f"  [skip] missing {tfile} or {pfile}")
            continue
        trades = pd.read_csv(tfile, sep=";")
        prices = pd.read_csv(pfile, sep=";")

        # mid lookup and forward-mid lookup per product
        mid = prices.pivot_table(index="timestamp", columns="product",
                                 values="mid_price")
        for _, tr in trades.iterrows():
            sym, ts, px, qty = tr["symbol"], tr["timestamp"], tr["price"], tr["quantity"]
            if sym not in mid.columns:
                continue
            series = mid[sym].dropna()
            if ts not in series.index:
                continue
            m_now = series.loc[ts]
            # forward mid: last quote at or before ts+H (stay within the day)
            fwd = series.loc[series.index <= ts + FORWARD_TICKS]
            m_fwd = fwd.iloc[-1] if len(fwd) else m_now
            if not np.isfinite(m_now) or m_now <= 0:
                continue
            fwd_ret_bps = (m_fwd - m_now) / m_now * 1e4  # underlying move, unsigned
            for cp, side in ((tr["buyer"], +1), (tr["seller"], -1)):
                if not isinstance(cp, str) or not cp.strip():
                    continue
                rows.append({
                    "cp": cp,
                    "qty": qty,
                    "signed_qty": side * qty,
                    # + = paid up vs mid (aggressive), - = better than mid (passive)
                    "edge_vs_mid": side * (px - m_now),
                    "signed_fwd_bps": side * fwd_ret_bps,
                    "win": 1 if side * fwd_ret_bps > 0 else 0,
                })
    return pd.DataFrame(rows)


def main():
    print("=" * 82)
    print("COUNTERPARTY FLOW CLASSIFICATION  (real round-4 trade logs)")
    print(f"Forward horizon = {FORWARD_TICKS} ticks; informed = market moves their way")
    print("=" * 82)

    led = build_ledger()
    if led.empty:
        print("No counterparty rows found.")
        return

    g = led.groupby("cp")
    tbl = pd.DataFrame({
        "n_trades": g.size(),
        "total_qty": g["qty"].sum(),
        "signed_vol": g["signed_qty"].sum(),
        "avg_edge_vs_mid": g["edge_vs_mid"].mean(),
        "fwd_ret_bps": led.groupby("cp").apply(
            lambda d: np.average(d["signed_fwd_bps"], weights=d["qty"]),
            include_groups=False,
        ),
        "win_rate": g["win"].mean(),
    })
    tbl["type"] = np.where(tbl["fwd_ret_bps"] > 0, "INFORMED", "noise")
    tbl = tbl.sort_values("fwd_ret_bps", ascending=False)

    pd.set_option("display.width", 200)
    print("\nRanked by forward return (quantity-weighted, signed by their side):\n")
    print(f"  {'counterparty':<12}{'n_trd':>7}{'tot_qty':>9}{'signed_vol':>11}"
          f"{'edge_vs_mid':>12}{'fwd_ret_bps':>12}{'win_rate':>9}  type")
    for cp, r in tbl.iterrows():
        print(f"  {cp:<12}{int(r.n_trades):>7}{int(r.total_qty):>9}"
              f"{int(r.signed_vol):>11}{r.avg_edge_vs_mid:>12.3f}"
              f"{r.fwd_ret_bps:>12.2f}{r.win_rate:>9.3f}  {r.type}")

    informed = tbl[tbl["type"] == "INFORMED"].index.tolist()
    noise = tbl[tbl["type"] == "noise"].index.tolist()
    print(f"\n  INFORMED (follow):  {', '.join(informed) if informed else '(none)'}")
    print(f"  NOISE (fade):       {', '.join(noise) if noise else '(none)'}")
    top = tbl.index[0]
    bot = tbl.index[-1]
    print(f"\n  Standout smart money : {top}  "
          f"(+{tbl.loc[top,'fwd_ret_bps']:.1f} bps forward, "
          f"win {tbl.loc[top,'win_rate']*100:.0f}%)")
    print(f"  Standout noise       : {bot}  "
          f"({tbl.loc[bot,'fwd_ret_bps']:.1f} bps forward, "
          f"win {tbl.loc[bot,'win_rate']*100:.0f}%)")

    # --- plot ----------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    order = tbl.sort_values("fwd_ret_bps")
    colors = ["#2a9d5c" if t == "INFORMED" else "#d1495b" for t in order["type"]]
    ax1.barh(order.index, order["fwd_ret_bps"], color=colors)
    ax1.axvline(0, color="k", lw=0.8)
    ax1.set_xlabel("Signed forward return, quantity-weighted (bps)")
    ax1.set_title(f"Counterparty edge over next {FORWARD_TICKS} ticks\n"
                  "(green = informed / follow, red = noise / fade)")
    for cp, r in order.iterrows():
        ax1.text(r["fwd_ret_bps"], cp, f" {int(r['n_trades'])} trd",
                 va="center", fontsize=8,
                 ha="left" if r["fwd_ret_bps"] >= 0 else "right")

    ax2.scatter(order["avg_edge_vs_mid"], order["fwd_ret_bps"],
                s=order["total_qty"] / order["total_qty"].max() * 400 + 40,
                c=colors, edgecolors="k", alpha=0.8)
    for cp, r in order.iterrows():
        ax2.annotate(cp, (r["avg_edge_vs_mid"], r["fwd_ret_bps"]),
                     fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax2.axhline(0, color="k", lw=0.6)
    ax2.axvline(0, color="k", lw=0.6)
    ax2.set_xlabel("Avg edge vs mid  (+ = aggressive / pays up)")
    ax2.set_ylabel("Signed forward return (bps)")
    ax2.set_title("Aggressiveness vs informativeness\n(bubble size = total volume)")
    fig.tight_layout()
    out = os.path.join(REPO, "plots", "counterparty_classification.png")
    fig.savefig(out, dpi=130)
    print(f"\nSaved plot -> {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main()
