# 📓 IMC Prosperity 4 — Full Competition Journal
## Team NEMO | IIT Bombay IEOR

This journal documents the full strategic evolution of Team NEMO during the IMC Prosperity 4 global trading challenge.

---

## 🏆 Competition Summary
- **Total Manual PnL:** ~382,000 XIRECs (2.5× Target)
- **Manual Rank:** #131 globally (Top 2%)
- **Algo Status:** Qualified for GOAT (Round 3-5), peak algorithmic performance in Round 4 (+25.8k).

---

## 🏗️ The 6-Lens Framework
For every product, we applied six analytical lenses before writing a single line of code:
1. **Price Series Shape:** Stationary, trending, or jumpy?
2. **Distribution:** Histogram centers and tails.
3. **Returns Volatility:** Tick-to-tick movement (σ).
4. **Autocorrelation:** Real signal vs. rounding artifacts (Lags 1-10).
5. **Viability Ratio:** Spread / σ ratio (Is market-making profitable?).
6. **Trade Flow:** Bot fingerprints and aggressive vs. passive balance.

---

## 🌊 Round 1 & 2: Foundations
**Products:** `INTARIAN_PEPPER_ROOT`, `ASH_COATED_OSMIUM`

### Strategy: Wall-Mid Market Making
- **Insight:** PEPPER had a perfect linear drift (+0.1/tick). OSMIUM was a stationary random walk.
- **Innovation:** Used Level-2 book order midpoints ("Wall-Mid") for a more stable fair value estimate than the jittery top-of-book mid.
- **MAF (Round 2):** Bid 15 in the Market Access Fee auction to secure 25% extra volume, which was mathematically worth ~10-15k in additional PnL.

---

## 🚀 Round 3: The Options Entry
**Products:** `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT` (VEV), 10 Vouchers (Calls)

### The Learning Curve
- Initial Round 3 result was **-2,740** due to lack of a proper Black-Scholes anchor.
- **Lesson:** Directional guessing in options is a recipe for liquidation. We needed a volatility-aware model.

---

## 💎 Round 4: The Predator & The Prey
**Products:** Same as Round 3 + Counterparty IDs

### The "Mark" Analysis
We computed the "edge vs mid" for all 7 named counterparties:
- **Mark 14 (Winner):** The "Predator". We followed their trades.
- **Mark 38 (Loser):** The "Prey". We consistently faded their trades.
- **Mark 22/01:** Structural volatility sellers/buyers.

### Volatility Discovery
- **Realized Vol:** 34.4% (Consistent across all days).
- **Implied Vol:** 20.3% (Locked IMC bot parameter).
- **The Edge:** Options were priced at 59% of fair value. The play was to **BUY** underpriced OTM vouchers.

---

## 📰 Manual Rounds: Game Theory & Math

### R1: Stale-Book Auction (+87k)
- **Strategy:** Bid just above the queue top to guarantee price priority while keeping clearing price favorable.

### R2: Three-Pillar Allocation (+201k | #131 Global)
- **Math:** Optimal Research:Scale ratio derived via calculus (23:77).
- **Game Theory:** Used Bayesian synthesis of past competition data to predict crowd clustering at `sp=48`.

### R3: Two-Bid Auction (+74k)
- **Strategy:** Placed bids at (775, 855). Learned that crowds overshoot Nash equilibrium more aggressively than models predict.

### R4: Options Pricing (+17k)
- **Highlight:** Identified a Risk-Free Chooser Arbitrage using the **Stulz Formula**.
- **Lesson:** 100-path simulations create high variance; mathematical expectation is the only true anchor.

### R5: News-Based Portfolio
- **Math:** Optimal allocation $V^* = Y/2$ where Y is the expected price move.
- **Calibration:** Tiers (1-5) based on news severity (Index inclusion > Fundamental growth > PR crisis).

---

## 🧠 Key Takeaways
1. **Suspiciously clean numbers are IMC tells.** A slope of exactly 0.001000 or a constant IV is a hardcoded bot parameter, not market noise.
2. **Lag-1 autocorrelation of -0.5 is a rounding artifact.** Always check higher lags.
3. **Past Prosperity data is the strongest signal.** Crowds in current rounds often mirror behaviors documented in past winner write-ups.
4. **Commit to the math.** Drifting from a calculated optimum to a "safer" feel-based number cost ~20,000 XIRECs across the competition.

---
*Team NEMO | IIT Bombay IEOR | Prosperity 4*
