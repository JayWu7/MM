# MM 🧠

**A modular, extensible passive market-making system** compatible with both **CEX** (Binance Spot) and **DEX** (Hyperliquid Derivatives), built around an order-book architecture. It supports multiple trading pairs and can be expanded to additional platforms.

---

## 🚀 Quick Start

1. **Install dependencies**

   ```bash
   git clone https://github.com/JayWu7/MM.git
   cd MM
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Edit config file**
   * Add your exchange API keys in auth.py.
   * Customize your market-making configuration by referring to the example files (e.g., MM/configs/test_hp_sui_auto.py).

3. **Launch the runner**

   ```bash
   python3 mm_run.py --config [config_name] 
   ```
---

## 🔍 Project Structure

```
MM/
├── configs/              # Configuration files for exchange API credentials, market maker strategy parameters, 
│                         # volatility settings, and hedging parameters.
│
├── exchange/             # Exchange connector implementations.
│   └── exchange_base.py  # Base class for all exchange connectors. 
│                         # Extend this when integrating new exchange support.
│
├── feeds/                # Market data modules for historical and live feeds.
│   ├── historical/       # Fetching and processing historical market data.
│   └── live/             # Real-time price feed handlers.
│       └── feeds_base.py # Base class for live data feeds. Extend this for new exchanges.
│
├── strategies/           # Implementation of market-making strategies.
│   ├── strategy_base.py  # Abstract base class for all strategies. 
│                         # Inherit from this when creating custom strategies.
│   ├── spot.py
│   ├── curve.py
│   ├── bid_ask.py
│   └── auto_mode.py
│
├── hedge/                # Inventory hedging modules, including passive hedging for crash protection 
│   │                     # and active hedging for real-time exposure control.
│   └── hedge.py
│
├── mm_run.py             # Main entry point for running the live passive mm trading system.
│
└── init_config.py        # CLI tool to easily initialize and customize strategy configurations.

```

---

## 🧠 Core Module Design

### 📐 1. Market Maker Strategies

#### 🧭  Design Philosophy

Each strategy relies on the real-time **order book mid-price** as a quoting anchor. It dynamically updates the number and price levels of bid/ask limit orders based on:

* **User-defined price range from mid-price** (upper and lower bounds),
* **Order price spacing** (`bin_step`), and
* **Inventory exposure ratio**.

To manage risk and avoid directional overexposure, the system calculates the live **inventory ratio** as:

```
inventory_ratio = inventory_value / quote_value
```

It then compares this ratio to the **initial inventory target** to derive the **Inventory-Quote Value Movement Ratio (IQV Movement Ratio)**:

```
iqv_movement_ratio = inventory_ratio / init_inventory_ratio
```

This `iqv_movement_ratio` is used to **dynamically and linearly adjust the size** of bid and ask orders. As the inventory drifts further from the target allocation, the system progressively reduces order sizes on the more exposed side—until the inventory returns to an acceptable risk band.

This creates a feedback loop where inventory risk is controlled **passively** through order sizing rather than immediate hedge execution, allowing for smoother mean-reversion and tighter capital efficiency.

To support extensibility, the system provides a flexible base class `strategy_base.py`, which enable easily implement custom strategies by inheriting from this base class and overriding the following method: ```compute_current_bins```

This design enables seamless plug-and-play of new strategies with minimal integration overhead.


#### ⚙️ Core Attributes

Each strategy defines the following core attributes to control quoting behavior and inventory risk:

| Attribute                                                         | Description                                                   |
| ----------------------------------------------------------------- | ------------------------------------------------------------- |
| `iqv_ratio`                                                       | Inventory ratio:                                              |
|    |   `iqv_ratio = inventory_value / (inventory_value + quote_value)`                                                            |
| `iqv_move_ratio`                                                  | IQV deviation from initial target:                            |
|   |     `iqv_move_ratio = (iqv_ratio - init_iqv_ratio) / init_iqv_ratio`                                                          |
| `price_up_pct_limit` , `price_down_pct_limit`                     | Upper/lower bound for order price as % from mid-price         |
| `bin_step`                                                        | Price gap between orders (in basis points, e.g. 20bp = 0.002) |
| `iqv_up_limit` , `iqv_down_limit`                                 | IQV bounds: stop placing buy/sell orders if exceeded          |
| `inventory_rb_iqv_ratio` , `quote_rb_iqv_ratio`                   | Thresholds to start linearly reducing buy/sell orders size    |
| `bins`                                                            | Output order quotes                                        |


#### 🧮 Core Methods

Each strategy implements or inherits the following core methods to control order sizing and quoting logic based on real-time inventory exposure:

* **`_compute_buy_size_multiplier()`**
  Returns a scaling factor ∈ \[0, 1] for adjusting **buy order size** based on `iqv_move_ratio`.

  * If `iqv_move_ratio ≤ inventory_rb_iqv_ratio` → return `1.0` (full size)
  * If `iqv_move_ratio ≥ iqv_up_limit` → return `0.0` (disable buying)
  * Else → linearly reduce size between these thresholds.

* **`_compute_sell_size_multiplier()`**
  Returns a scaling factor ∈ \[0, 1] for adjusting **sell order size** based on `iqv_move_ratio`.

  * If `iqv_move_ratio ≥ quote_rb_iqv_ratio` → return `1.0` (full size)
  * If `iqv_move_ratio ≤ iqv_down_limit` → return `0.0` (disable selling)
  * Else → linearly reduce size between these thresholds.

* **`compute_current_bins(current_price, cur_inventory_amount, cur_quote_amount)`**
  Abstract method to generate bid and ask levels (bins) based on the mid-price and current position.
  Must be implemented by each strategy subclass. Returns:

  ```python
  {
    'bids': [(price1, size1), (price2, size2), ...],
    'asks': [(price1, size1), (price2, size2), ...]
  }
  ```

#### 🚀 Implemented Strategies

| Strategy      | Description                                                                                                                                | Best For                                  | Notes                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------- | ------------------------------------------------------------------- |
| **Spot**      | Uniform distribution across the full price range                                                                                           | General-purpose, low-touch LP             | Simple & robust, rebalances infrequently                            |
| **Curve**     | Concentrates liquidity near mid-price                                                                                                      | Stable pairs, tight ranges                | Efficient in calm markets; rebalancing needed as price drifts       |
| **Bid-Ask**   | Inverse curve — liquidity concentrated at both ends                                                                                        | Volatile markets, DCA flows               | High volatility capture; more frequent rebalancing required         |
| **Auto-Mode** | Dynamically selects strategy based on volatility thresholds:<br>• vol < `lower` → Curve<br>• vol > `upper` → BidAsk<br>• in between → Spot | Adaptive markets with changing volatility | Uses `vol_lower_threshold` and `vol_upper_threshold` to auto-switch |

<sub>📝 Strategy logic inspired by [Meteora](https://www.meteora.ag/)'s dynamic liquidity model.</sub>

#### 📦 Order Distribution Strategies: `compute_current_bins` Overview

##### Curve Strategy

* Concentrates liquidity near the mid-price.
* Order sizes decrease exponentially with distance from the center bin:
  size for bin *i* = max\_size × (decay\_rate) ^ i
* Sizes normalized to available inventory and quote balances, then scaled by risk multipliers.
* Prices spaced evenly by fixed step (`bin_step`).
* Ideal for stable or low-volatility markets.

##### Bid-Ask Strategy

* Places smaller orders near mid-price, increasing sizes further away to capture large swings.
* Order weights inversely proportional to geometric decay:
  weight for bin *i* = 1 / (decay\_rate ^ (i+1) + ε)
* Weights normalized to total capital available per side.
* Risk multipliers adjust final order sizes.
* Suitable for volatile markets with large price moves.

---

### 📊 2. Volatility Estimation

#### 🎯 Design Philosophy
This module estimates market volatility by combining short-term, long-term, and exponentially weighted moving average (EWMA) models. The goal is to provide a smooth yet responsive volatility measure that adapts to recent price changes while incorporating historical trends.

#### ⚙️ Calculation Method

* Compute log returns from price data.
* Calculate **short-term volatility** using the standard deviation of recent returns over a short window (default 60 points).
* Calculate **long-term volatility** similarly over a longer window (default 600 points).
* Update an **EWMA volatility** that weights recent squared returns with a smoothing factor (`ewma_lambda`, default 0.94).
* Combine the three measures into a weighted **effective volatility**:
  `effective_vol = 0.3 * short_vol + 0.4 * ewma_vol + 0.3 * long_vol`
* Volatility values are annualized by scaling with the square root of 3600 (assuming 60 price points per hour or relevant timeframe).

#### 🚀 Usage

1. Initialize the estimator with optional parameters for window sizes and EWMA lambda:

   ```python
   vol_estimator = VolatilityEstimator(short_window=60, long_window=600, ewma_lambda=0.94)
   ```
2. Feed a chronological list of prices (latest last) to update volatility estimates:

   ```python
   vol_metrics = vol_estimator.update(price_series)
   ```
3. `vol_metrics` returns a dictionary with keys:

   * `"short_vol"`: Short-term volatility estimate
   * `"long_vol"`: Long-term volatility estimate
   * `"ewma_vol"`: EWMA volatility estimate
   * `"effective_vol"`: Combined volatility used in strategy decisions

---

### 🛡️ 3. Hedge Mechanisms

#### 🎯 Design Philosophy

The Hedge module is designed to **minimize portfolio risk** and **reduce exposure to extreme price movements** in a passive market-making system. It supports both:

* **Active Hedging** — Automatically rebalances inventory when position exposure (IQV movement) exceeds a defined threshold.
* **Passive Hedging** — Pre-sets trigger orders to protect against sudden market crashes or spikes, and auto-hedges when those triggers are hit.

##### Key design goals:

* 📉 **Crash protection**: Through trigger-based passive hedge orders that are placed off-market and executed when a price threshold is crossed.
* 📈 **Exposure control**: Actively monitors inventory-to-quote balance and takes corrective actions when deviation exceeds the configured safe range.
* 🔁 **Dual-sided control**: Allows flexible hedging configuration — either hedge both upward and downward price movements to mitigate impermanent loss from sharp rallies, or hedge only against price crashes to preserve capital in bear scenarios.
* 🔄 **Dynamic Passive Trigger Updates**: When the position approaches delta-neutral, the system recalculates and refreshes passive hedge trigger orders to align with the updated price and exposure.
* ⚖️ **Adaptive sizing**: Hedge size is dynamically computed based on real-time inventory, quote balance, and price to precisely rebalance back to a healthy IQV (Inventory Quote Value) ratio.
* ⏱️ **Asynchronous design**: Runs continuous monitoring loops (`active_hedge_monitor`, `passive_hedge_monitor`) in the background to respond in real time with minimal latency.


#### ⚙️ Core Attributes

| Attribute                         | Description                                                                                          |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `passive_hedge_ratio`             | Deviation threshold from delta-neutral price to **trigger passive hedge orders** (crash protection). |
| `active_hedge_iqv_ratio`          | Inventory-Quote-Value (IQV) movement ratio that **triggers active hedging** to reduce exposure.      |
| `passive_hedge_sp_ratio`          | **Stop-loss ratio** for passive hedge positions, placed relative to trigger price.                   |
| `passive_hedge_proportion`        | Portion of total inventory **passively hedged** during crash events (e.g. 0.5 = 50%).                |
| `passive_hedge_refresh_iqv_ratio` | IQV movement threshold to **refresh passive trigger orders** when returning near delta-neutral.      |


#### 🧷 Passive Hedge Logic

**Passive Hedge** is a volatility-triggered strategy that automatically enters hedging positions when the price deviates significantly from a delta-neutral zone. It is designed to prevent major losses from sharp market moves.


##### ⛓️ Workflow Overview:

| Phase                   | Description                                                                                                                                                                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🕵️‍♂️ *Monitoring*     | Periodically (every `passive_hedge_refresh_interval` seconds) check if a passive hedge is currently active.                                                                                                                                                                              |
| 📉 *Trigger Activation* | If **not** in a passive hedge position:<br>1. Monitor both long and short trigger orders.<br>2. If a trigger order is **filled**:<br> • Record the entry price.<br> • Calculate the stop-loss price using `passive_hedge_sp_ratio`.<br> • Submit a stop-loss order to exit the hedge position if price reverts. |
| 📊 *Dynamic Refresh*    | If the IQV (Inventory Quote Value) movement returns to a neutral range:<br> • Update long/short trigger prices using current market price ± `passive_hedge_ratio`.<br> • Recalculate hedge size based on current inventory and `passive_hedge_proportion`.   <br> • Cancel any existing trigger orders.<br> • Re-submit trigger orders using the new parameters.                  |
| 🔁 *Ensure Coverage*    | If any trigger orders are missing (e.g., cancelled or failed), re-submit them based on the current hedge configuration (`dual_sided_hedge`).                                                                                                                                             |
| 💥 *Exit Hedge*         | If the stop-loss order is filled:<br> • Mark the current hedge round as complete.<br> • Reset the state and prepare for the next cycle.                                                                                                                                                                |

##### 🧮 Key Calculations:

* **Trigger Prices**

  * Long Trigger Price = `current_price * (1 + passive_hedge_ratio)`
  * Short Trigger Price = `current_price * (1 - passive_hedge_ratio)`

* **Stop-Loss Price** (calculated after trigger order is filled)

  * Long Side: `entry_price * (1 - passive_hedge_sp_ratio)`
  * Short Side: `entry_price * (1 + passive_hedge_sp_ratio)`

* **Hedge Size**

  * `passive_hedge_size = cur_inventory_amount * passive_hedge_proportion`

##### ⚙️ Notable Features:

* 🔄 **Dynamic Adjustment**: Hedge orders are recalibrated when IQV returns close to delta-neutral, ensuring the strategy adapts to changing conditions.
* ⚖️ **Dual-Sided Hedge Option**: With `dual_sided_hedge = True`, both upward and downward volatility can be hedged.
* 🛑 **Stop-Loss Protection**: Every passive hedge entry includes a predefined stop-loss to cap potential losses.


#### 🧠 Active Hedge Logic

The Active Hedge mechanism dynamically manages inventory exposure by continuously monitoring the Inventory Quote Value (IQV) Movement ratio and adjusting the position to maintain it within a target range. This helps control risk by reducing or increasing the inventory when deviations become significant.


##### ⛓️ Workflow Overview

| Phase             | Description                                                                                                                                                                                              |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🕵️‍♂️ *Monitoring*    | Continuously track the IQV movement ratio: `(current IQV - initial IQV) / initial IQV`.                                                                                                                  |
| 📉 *Evaluate Trigger* | Determine if the IQV movement exceeds upper or lower thresholds. If above the upper threshold, reduce inventory (short). If below the lower threshold and dual-sided hedge is enabled, increase inventory (long). |
| 📊 *Calculate Size*   | Compute the hedge size `x` required to bring the IQV back to the target threshold, based on current inventory and quote balances.                                                                        |
| ✅ *Place Orders*     | Place post-only GTX limit orders to minimize slippage; if partially unfilled, submit market orders to ensure execution.                                                                                  |
| 🔁 *Update Hedge State*     | Record the current hedge position size to avoid duplicate or conflicting orders.                                                                                                                         |
| 🔄 *Repeat*      | Continuously repeat this process at a fixed interval (every second).                                                                                                                                     |


##### 🧮 Key Calculations

Let:

* `i` = current inventory amount (base asset)
* `p` = current price
* `q` = current quote amount (quote asset)
* `N` = target IQV threshold = `initial IQV × active_hedge_iqv_ratio`

The Inventory Quote Value (IQV) ratio is calculated as:

```markdown
IQV = \frac{i \times p}{i \times p + q}
```

To solve for hedge size `x` (amount to buy or sell) that brings IQV back to target `N`:

* **For reducing inventory (selling):**

```markdown
\frac{(i - x) \times p}{(i - x) \times p + q + x \times p} = N
```

Solving for `x` gives:

```markdown
x = \frac{i p - N i q - N q}{p}
```

* **For increasing inventory (buying, when dual-sided hedge is enabled):**

```markdown
\frac{(i + x) \times p}{(i + x) \times p + q - x \times p} = N
```

Solving for `x` gives:

```markdown
x = \frac{N i q + N q - i p}{p}
```

#### ⚙️ Notable Features

* 🧮 Uses precise mathematical formulas to calculate hedge sizes ensuring IQV ratio is actively controlled.
* ⚡ Prefers GTX (post-only) limit orders to reduce slippage and avoid immediate fills at unfavorable prices.
* ⏱️ Operates continuously with second-level frequency for real-time risk management and position adjustment.

---


## 📅 Todo

* 🔜 Use WebSocket to monitor order status for further latency reduction
* 🔜 Build monitoring dashboard & metrics visualization
* 🔜 Add a backtesting engine with analytics


---

## 📄 License

This project is licensed under the MIT License.

---

## 📬 Contact

For questions, feedback, or collaboration opportunities, feel free to reach out:

* **Name**: Boreas Wu
* **Email**: `boreas.testamento@gmail.com`
* **GitHub**: [@JayWu7](https://github.com/JayWu7)
* **Twitter**: [@boreaswu](https://x.com/boreaswu)
