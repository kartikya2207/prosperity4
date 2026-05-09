# 📈 Algorithmic Competition & Learning Journey
### 🏆 Team NEMO | IMC Prosperity 4 & Competitive Poker Bots

This repository serves as a professional journal for my journey into quantitative trading and competitive algorithmic challenges. Both projects featured here were high-stakes global competitions that served as massive learning catalysts for my growth in data science, finance, and game theory.

---

## 🌊 IMC Prosperity 4: Quantitative Trading
**Status:** High-Effort Learning Project | **Peak Performance:** Rank 1 Globally (Manual Round 1)

My participation in IMC Prosperity 4 was a journey of "learning by doing." While our final standing was #1501 overall, the project was a success in strategic evolution—starting from simple mid-price models and progressing to complex Black-Scholes volatility arbitrage.

![Final Leaderboard](plots/final_leaderboard.png)

### 🚀 Key Learning Milestones
- **Round 1 (Rank 1 Globally):** Mastered auction game theory and stale-book dynamics.
- **The Options Pivot:** After a loss in Round 3, I reverse-engineered the bot's hidden parameters to identify a structural 1.7x gap between Implied and Realized volatility.
- **Mark Analysis:** Learned to build real-time ledgers to categorize counterparty behaviors into "Smart Money" vs. "Noise."

---

## ♠️ Poker Bot Competition: Strategic Game Theory
**Status:** Parallel Learning Track

In addition to quantitative finance, I applied similar algorithmic principles to a competitive Poker Bot challenge. This project focused on:
- **Nash Equilibrium:** Implementing GTO (Game Theory Optimal) strategies.
- **Exploitative Play:** Building models to detect and punish opponent leaks (similar to the "Mark" analysis in Prosperity).
- **Risk Management:** Managing bankroll variance through Kelly Criterion-inspired sizing.

---

## 🧠 The Philosophy: Continuous Improvement
Neither of these projects is "finished." I view them as living foundations. My goal isn't just to rank, but to understand the mathematical "why" behind every move.
- **Iteration:** I am constantly refining the `trader.py` and my poker logic as I learn more about stochastic processes and machine learning.
- **Transparency:** I showcase the wins (Rank 1 Round 1) and the losses (Round 3 Options) equally because the learning comes from the gap between them.

---
*Developed by Team NEMO | Focused on Quantitative Excellence and Strategic Growth.*


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
