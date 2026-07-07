"""
VEV voucher implied-vs-realized volatility analysis.
================================================================================

Loads the REAL round-4 VELVETFRUIT_EXTRACT (underlying) and VEV_<strike>
(voucher / European call) price data, backs out the implied volatility the IMC
market-maker bots were quoting per strike, and compares it against the
volatility the underlying actually realized over the same window.

Run from the repo root:

    python src/analysis/vol_mispricing.py

Outputs:
  * a printed per-strike implied-vol table and the implied-vs-realized summary
  * plots/iv_vs_realized.png

Modelling assumptions (documented so the numbers can be reproduced/challenged):
  * VEV_<strike> is a European call on VELVETFRUIT_EXTRACT, r = 0, no dividends.
  * Time to expiry T = 7 trading days = 7/250 yr. This is the Prosperity voucher
    convention; the bots quoted a *constant* price/IV that does not decay across
    the sample, so a fixed T recovers the locked IV they were using. IV scales
    as ~1/sqrt(T), so the absolute level is sensitive to this assumption -- but
    the strike-to-strike flatness and the direction of the implied-vs-realized
    gap are not.
  * Annualization: 10,000 price samples per trading day, 250 trading days/yr.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from black_scholes import implied_vol, realized_vol, parkinson_vol

# --- configuration -----------------------------------------------------------
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_FILES = [
    os.path.join(REPO, "data", "round4", f"prices_round_4_day_{d}.csv")
    for d in (1, 2, 3)
]
UNDERLYING = "VELVETFRUIT_EXTRACT"
# Near-the-money strikes with meaningful, numerically-stable time value.
# Deep ITM (4000/4500/5000) has negligible time value; deep OTM (6000/6500)
# is pinned at the 0.5 price floor -- neither yields a reliable IV.
STRIKES = [5100, 5200, 5300, 5400, 5500]
T_YEARS = 7 / 250
SAMPLES_PER_DAY = 10_000
DAYS_PER_YEAR = 250
PERIODS_PER_YEAR = SAMPLES_PER_DAY * DAYS_PER_YEAR


def load_days():
    frames = []
    for f in DATA_FILES:
        if not os.path.exists(f):
            print(f"  [skip] missing data file: {f}")
            continue
        df = pd.read_csv(f, sep=";")
        df["_srcday"] = os.path.basename(f)
        frames.append(df)
    if not frames:
        sys.exit("No round-4 price files found -- cannot run vol analysis.")
    return frames


def main():
    print("=" * 78)
    print("VEV VOUCHER: IMPLIED (bot-quoted) vs REALIZED VOLATILITY")
    print("Data: round 4, days 1-3 (real IMC price files)")
    print(f"Assumptions: European call, r=0, T={T_YEARS:.4f}yr (7 trading days)")
    print("=" * 78)

    frames = load_days()

    # --- realized volatility of the underlying (same window) -----------------
    rv_c2c, rv_park = [], []
    for df in frames:
        und = (
            df[df["product"] == UNDERLYING]
            .sort_values("timestamp")["mid_price"]
            .to_numpy(dtype=float)
        )
        rv_c2c.append(realized_vol(und, PERIODS_PER_YEAR))
        # Parkinson: build 100-sample bars, take high/low of the mid in each bar
        n = (und.size // 100) * 100
        bars = und[:n].reshape(-1, 100)
        rv_park.append(
            parkinson_vol(bars.max(axis=1), bars.min(axis=1), PERIODS_PER_YEAR)
        )
    realized_c2c = float(np.nanmean(rv_c2c))
    realized_parkinson = float(np.nanmean(rv_park))

    # --- implied volatility per strike (bot quotes) --------------------------
    print("\nPer-strike implied volatility (averaged over all quotes in window):")
    print(f"  {'strike':>7} {'moneyness':>10} {'mean_mid':>9} {'impl_vol':>9} "
          f"{'std':>7} {'n':>7}")
    per_strike_iv = {}
    for K in STRIKES:
        col = f"VEV_{K}"
        ivs, mids, spots = [], [], []
        for df in frames:
            piv = df.pivot_table(index="timestamp", columns="product",
                                 values="mid_price")
            if col not in piv or UNDERLYING not in piv:
                continue
            S = piv[UNDERLYING].to_numpy(dtype=float)
            P = piv[col].to_numpy(dtype=float)
            for s, p in zip(S, P):
                if np.isfinite(s) and np.isfinite(p):
                    v = implied_vol(p, s, K, T_YEARS)
                    if np.isfinite(v):
                        ivs.append(v)
                    mids.append(p)
                    spots.append(s)
        if ivs:
            iv_mean = float(np.mean(ivs))
            per_strike_iv[K] = iv_mean
            moneyness = float(np.mean(spots)) / K
            print(f"  {K:>7} {moneyness:>10.3f} {np.mean(mids):>9.2f} "
                  f"{iv_mean:>9.4f} {np.std(ivs):>7.4f} {len(ivs):>7}")

    implied = float(np.mean(list(per_strike_iv.values())))
    iv_spread = float(max(per_strike_iv.values()) - min(per_strike_iv.values()))

    # --- summary -------------------------------------------------------------
    print("\n" + "-" * 78)
    print(f"Mean IMPLIED vol (bot quotes, across strikes) : {implied:6.4f}  "
          f"({implied*100:.1f}%)")
    print(f"  strike-to-strike IV spread (flatness check) : {iv_spread:6.4f}  "
          f"({iv_spread*100:.1f} vol pts)")
    print(f"REALIZED vol close-to-close (underlying)       : {realized_c2c:6.4f}  "
          f"({realized_c2c*100:.1f}%)   <- headline estimate")
    print(f"REALIZED vol Parkinson (underlying, 100-bars)  : {realized_parkinson:6.4f}  "
          f"({realized_parkinson*100:.1f}%)   <- INFLATED by tick microstructure")
    print("  (Parkinson high/low over 100-tick bars is dominated by bid-ask bounce")
    print("   and tick rounding here, so it massively overstates true vol -- we do")
    print("   NOT use it for the headline; close-to-close is the credible estimate.)")
    print(f"RATIO realized(c2c) / implied                  : "
          f"{realized_c2c/implied:6.2f}x")
    edge = "UNDERPRICED (realized > implied -> long-vol edge)" if realized_c2c > implied \
        else "OVERPRICED (implied > realized -> short-vol edge)"
    print(f"Verdict: vouchers were {edge}")
    print("-" * 78)

    # --- plot ----------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ks = list(per_strike_iv.keys())
    vals = [per_strike_iv[k] * 100 for k in ks]
    ax.bar([str(k) for k in ks], vals, color="#3b6fb0", label="Bot-quoted implied vol")
    ax.axhline(realized_c2c * 100, color="#d1495b", ls="--", lw=2,
               label=f"Realized vol (close-to-close) = {realized_c2c*100:.1f}%")
    ax.axhline(implied * 100, color="#2b2b2b", ls="-", lw=1, alpha=0.5,
               label=f"Mean implied vol = {implied*100:.1f}%")
    ax.annotate(f"{realized_c2c/implied:.1f}x gap",
                xy=(len(ks) - 1, (implied * 100 + realized_c2c * 100) / 2),
                ha="right", va="center", fontsize=11, color="#d1495b",
                fontweight="bold")
    for k, v in zip(ks, vals):
        ax.text(str(k), v + 0.3, f"{v:.1f}", ha="center", fontsize=9)
    ax.set_xlabel("VEV voucher strike")
    ax.set_ylabel("Annualized volatility (%)")
    ax.set_title("VEV vouchers: bot-quoted implied vol vs realized vol "
                 "(round 4, days 1-3)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = os.path.join(REPO, "plots", "iv_vs_realized.png")
    fig.savefig(out, dpi=130)
    print(f"\nSaved plot -> {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main()
