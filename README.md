# 📈 IMC Prosperity 4 — Team NEMO
### 🏆 Manual Rank 1 (Round 1) | Final Standings: #1075 Manual, #1501 Overall

Welcome to the official repository for **Team NEMO's** participation in the **IMC Prosperity 4** challenge. This project showcases the intersection of quantitative finance, game theory, and high-frequency algorithmic trading strategies.

![Final Leaderboard](plots/final_leaderboard.png)

---

## 🚀 Highlights
- **Manual Performance:** **Rank 1 Globally in Round 1** (+87,995 XIRECs).
- **Final Standing:** Ranked #1075 in Manual, #1501 Overall out of 20,000+ participants.
- **Algorithmic Edge:** Engineered a multi-layer strategy combining Black-Scholes volatility arbitrage with counterparty "Mark" behavioral analysis.
- **Top Strategy:** Identified a risk-free arbitrage in Round 4 using the **Stulz Formula** for chooser options.

---

## 📁 Repository Structure
```text
├── datamodel.py             # Official IMC data model
├── trader.py                # Final algorithmic trading submission
├── JOURNAL.md               # Detailed strategic evolution & manual logs
├── STRATEGY_PLAYBOOK.md     # Engineering & iteration guidelines
├── src/
│   ├── round_1_2/           # Stationary MR & Linear Drift strategies
│   └── round_3_5/           # Volatility Arbitrage & Options models
├── analysis/                # EDA and strategy validation notebooks
└── data/                    # Sample price and trade logs from the competition
```

---

## 🛠️ Core Strategies

### 1. Volatility Arbitrage (Vouchers)
We reverse-engineered the IMC bot's pricing and discovered that implied volatility was locked at **20.3%**, while realized volatility was consistently **34.4%**. This 1.7× gap created a massive structural edge for buying underpriced options (long gamma).

### 2. Counterparty Behavioral Analysis (The Marks)
In Round 4, counterparty IDs were revealed. We built a real-time ledger to track the PnL of each bot:
- **Mark 14:** Identified as a "Smart" bot. Our strategy followed their signals.
- **Mark 38:** Identified as "Noise/Prey". We systematically faded their trades for consistent spread capture.

### 3. Linear Trend Drift (Pepper Root)
Discovered a perfectly engineered linear drift of **0.001000 ticks/timestamp**. We implemented a directional long strategy with a custom OLS slope-based reversal exit to protect against trend shifts.

### 4. Wall-Mid Fair Value
Developed a proprietary "Wall-Mid" fair value estimate using Level-2 order book depth, providing a more robust anchor for market-making than standard top-of-book midpoints.

---

## 📊 Manual Round Performance
Our team excelled in the game theory and mathematical optimization rounds:
- **Round 1 (Stale-Book Auction):** Achieved **Rank 1 Globally** with a perfect bidding strategy.
- **Round 2 (Resource Allocation):** Achieved **92.4% of theoretical maximum** (#131 rank for this round).
- **Round 4 (Options Arbitrage):** Successfully identified and traded a chooser-option arbitrage, locking in risk-free profit.

---

## 👨‍💻 Tech Stack
- **Language:** Python 3.11 (Standard Library only for submission)
- **Frameworks:** Custom backtesting engine, 6-Lens Analysis framework.
- **Math:** Black-Scholes (Abramowitz & Stegun Approximation), OLS Regression, Bayesian Inference.

---

## 📖 Lessons Learned
- **Robustness > Peak:** A "flat-good" strategy that performs consistently across all days is superior to a "peak-great" strategy that overfits to a single lucky day.
- **Data Hygiene:** Filtering garbage rows (mid_price ≤ 0) is essential. Small data impurities can poison complex statistical models.
- **Game Theory:** In crowd-based auctions, the winning move is often just above the Nash equilibrium where most "smart" players cluster.

---
*Developed by Team NEMO at IIT Bombay (IEOR).*
