---

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

To support extensibility, the system provides a flexible base class `strategy_base.py`, which enable easily implement custom strategies by inheriting from this base class and overriding the following method:

```python
def compute_current_bins(self, current_price: float, cur_inventory_amount: float, cur_quote_amount: float) -> dict:
    """
    Return the current bin (price levels and order sizes) based on live market and position state.
    """
```

This design enables seamless plug-and-play of new strategies with minimal integration overhead.

当然，下面是你提供的 `Core Attributes` 内容的**精简英文版本**，保留核心含义与公式，适合用于 README 中快速传达关键信息：

---

#### ⚙️ Core Attributes

Each strategy uses the following key attributes to generate and scale passive orders:

| Attribute                                                                         | Description                                                           |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `iqv_ratio`                                                                       | Inventory ratio:                                                      |
|   $\frac{\text{inventory\_value}}{\text{inventory\_value} + \text{quote\_value}}$ |                                                                       |
| `iqv_move_ratio`                                                                  | Deviation from target:                                                |
|   $\frac{\text{iqv\_ratio} - \text{init\_iqv\_ratio}}{\text{init\_iqv\_ratio}}$   |                                                                       |
| `price_up_pct_limit` , `price_down_pct_limit`                                     | Max/min % distance from mid-price for order placement                 |
| `bin_step`                                                                        | Price step (in basis points) between quote levels (e.g. 20bp = 0.002) |
| `iqv_up_limit` , `iqv_down_limit`                                                 | Stop buying/selling if IQV deviation exceeds these bounds             |
| `inventory_rb_iqv_ratio` , `quote_rb_iqv_ratio`                                   | Start linearly reducing buy/sell sizes beyond these thresholds        |
| `bins`                                                                            | Final computed bid/ask quotes:                                        |

```python
{'bids': [(price, size), ...], 'asks': [(price, size), ...]}
```


   * Core Methods
   * Exposure Management
   * Implemented Strategies


   * Volatility-aware distribution
     *(Mathematical models and class structure explanation)*

2. **🛡️ Hedge Mechanisms**

   * Passive Hedge (crash mitigation)
   * Active Hedge (real-time exposure rebalance)
   * Trigger logic, hedge sizing, and execution behavior
     *(Hedging formula, execution flow, and inventory delta calculations)*

3. **📊 Volatility Estimation**

   * Real-time rolling volatility window
   * Volatility model options (simple, EWMA, etc.)
   * How volatility feeds into strategy decisions
     *(Formulas, update interval, and integration into AutoMode)*

4. **🧩 Integration Logic**

   * How Strategies, Hedge, and Volatility modules interact
   * Rebalancing & Order Adjustment Cycle
   * Event-driven vs polling-driven behavior

---

### 📎 Each Subsection Will Include:

* **Conceptual Explanation**
* **Mathematical Formulas / Algorithms**
* **Implementation Notes / Class References**
* **Real-world Use Example (YAML Config Snippet or Code Sample)**

---


---


## 📅 Todo

* ✅ Official support: Binance Spot, Hyperliquid Derivatives
* 🔜 Add more CEX (OKX, Bybit) and DEX (dYdX, Vertex)
* 🔜 Build monitoring dashboard & metrics visualization
* 🔜 Add a backtesting engine with analytics

---

## 📄 License

This project is licensed under the **MIT License**.

---
