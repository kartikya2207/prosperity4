"""
Black-Scholes option pricing and volatility toolkit.
================================================================================

Self-contained helpers used by ``vol_mispricing.py`` to back out the implied
volatility that the IMC market-maker bots were quoting on the VELVETFRUIT_EXTRACT
(VEV) vouchers, and to compare it against the volatility the underlying actually
realized over the same window.

The VEV_<strike> instruments are European call options on VELVETFRUIT_EXTRACT
(strike = the number in the symbol). We assume zero interest rate and no
dividends, which is the standard convention for the Prosperity voucher market
(everything is quoted in XIRECs with no carry).

All functions are pure and depend only on numpy + scipy.stats.norm.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


# ------------------------------------------------------------------------------
# Core Black-Scholes building blocks
# ------------------------------------------------------------------------------
def d1(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """First Black-Scholes auxiliary term.

    Parameters
    ----------
    S : spot price of the underlying
    K : strike price
    T : time to expiry in *years*
    sigma : volatility (annualized, e.g. 0.20 for 20%)
    r : risk-free rate (default 0)
    """
    return (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))


def d2(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Second Black-Scholes auxiliary term: d2 = d1 - sigma*sqrt(T)."""
    return d1(S, K, T, sigma, r) - sigma * np.sqrt(T)


def bs_call_price(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Black-Scholes price of a European call.

    Degenerate cases (T<=0 or sigma<=0) return the intrinsic value max(S-K, 0),
    so the function is safe to call at expiry or with a zero-vol guess.
    """
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    _d1 = d1(S, K, T, sigma, r)
    _d2 = _d1 - sigma * np.sqrt(T)
    return S * norm.cdf(_d1) - K * np.exp(-r * T) * norm.cdf(_d2)


def bs_vega(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Sensitivity of the call price to a change in volatility (per 1.0 of vol)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    return S * norm.pdf(d1(S, K, T, sigma, r)) * np.sqrt(T)


# ------------------------------------------------------------------------------
# Implied volatility
# ------------------------------------------------------------------------------
def implied_vol(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float = 0.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float:
    """Back out the implied volatility from an observed call price.

    Uses Newton-Raphson seeded at sigma=0.3 and falls back to bisection if a
    Newton step leaves the bracket [1e-4, 5.0]. Returns ``np.nan`` when the
    quoted price is at or below intrinsic value (no positive time value, so no
    finite IV exists).
    """
    intrinsic = max(S - K, 0.0)
    if not np.isfinite(price) or price <= intrinsic + 1e-9:
        return np.nan

    lo, hi = 1e-4, 5.0
    sigma = 0.3
    for _ in range(max_iter):
        diff = bs_call_price(S, K, T, sigma, r) - price
        if abs(diff) < tol:
            return sigma
        # maintain a valid bracket for the bisection fallback
        if diff > 0:
            hi = sigma
        else:
            lo = sigma
        vega = bs_vega(S, K, T, sigma, r)
        if vega > 1e-8:
            step = diff / vega
            new_sigma = sigma - step
            if lo < new_sigma < hi:
                sigma = new_sigma
                continue
        sigma = 0.5 * (lo + hi)  # bisection fallback
    return sigma


# ------------------------------------------------------------------------------
# Realized volatility estimators
# ------------------------------------------------------------------------------
def realized_vol(prices: np.ndarray, periods_per_year: float) -> float:
    """Close-to-close annualized realized volatility.

    Standard deviation of consecutive log returns, scaled by
    sqrt(periods_per_year). ``prices`` is a 1-D array of mid prices sampled at a
    fixed cadence; ``periods_per_year`` is how many such samples fit in a year.
    """
    prices = np.asarray(prices, dtype=float)
    prices = prices[np.isfinite(prices) & (prices > 0)]
    if prices.size < 3:
        return np.nan
    rets = np.diff(np.log(prices))
    return float(np.std(rets, ddof=1) * np.sqrt(periods_per_year))


def parkinson_vol(
    high: np.ndarray, low: np.ndarray, periods_per_year: float
) -> float:
    """Parkinson high-low range volatility estimator (annualized).

    More efficient than close-to-close when intraperiod high/low are available.
    sigma^2 = (1 / (4 ln 2)) * mean( ln(high/low)^2 ), then annualized.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    mask = np.isfinite(high) & np.isfinite(low) & (low > 0)
    high, low = high[mask], low[mask]
    if high.size < 1:
        return np.nan
    hl = np.log(high / low) ** 2
    var_per_period = hl.mean() / (4.0 * np.log(2.0))
    return float(np.sqrt(var_per_period * periods_per_year))


if __name__ == "__main__":
    # Tiny self-test / round-trip: price at 20% vol, recover ~20% from the price.
    S, K, T = 5248.0, 5300.0, 7 / 250
    c = bs_call_price(S, K, T, 0.20)
    print(f"call(S={S}, K={K}, T={T:.4f}, vol=20%) = {c:.4f}")
    print(f"implied_vol(price={c:.4f}) = {implied_vol(c, S, K, T):.6f}")
