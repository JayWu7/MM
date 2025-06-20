# binance btc auto-mm paras

# === Token & Market Settings ===
UNDERLYING_TOKEN = "SUI"        # Base token for trading
QUOTE_TOKEN = "USDC"            # Quote currency used for pricing
MARKETPLACE = "binance_spot"    # Market where MM operates
HEDGE_MARKETPLACE = "binance_perp"  # Market used for hedging

# === Market Making Parameters ===
MM_UPDATE_INTERVAL = 30          # Interval (sec) to Update Market Maker Orders
MM_PRICE_UP_PCT_LIMIT = 0.02     # Max price increase from center price
MM_PRICE_DOWN_PCT_LIMIT = 0.02   # Max price drop from center price
MM_BIN_STEP = 40               # in basis points (bps), e.g. 25 means 0.25%
MM_INIT_INVENTORY_AMOUNT = 20.0   # Initial inventory amount
MM_INIT_QUOTE_AMOUNT = 100.0   # Initial quote balance
MM_MODE = "auto"                  # MM mode: [spot, curve, bid-ask, auto]
MM_LIVE_ORDER_NUMS = 10          # Number of live MM orders
MM_MIN_ORDER_SIZE = 0.1        # Minimum size for MM orders
MM_MAX_ORDER_SIZE = 5         # Maximum size for MM orders
MM_IQV_UP_LIMIT = 0.6           # Upper bound of inventory/quote movement ratio 
MM_IQV_DOWN_LIMIT = -0.6          # Lower bound of inventory/quote movement ratio
MM_INVENTORY_RB_IQV_RATIO = 0.3  # Rebalance when inventory/quote movement ratio > this
MM_QUOTE_RB_IQV_RATIO = -0.3     # Rebalance when inventory/quote movement ratio < this

# === Auto MM Volatility Controls ===
AUTO_MM_VOL_LOWER_THRESHOLD = 5  # Min vol to activate auto MM
AUTO_MM_VOL_UPPER_THRESHOLD = 25  # Max vol to stop auto MM

# === Hedge Parameters ===
HG_PASSIVE_HEDGE_RATIO = 0.0225         # Distance from current detal-neutral price for passive hedge
HG_MIN_HEDGE_ORDER_SIZE = 0.1        # Minimum hedge order size
HG_ACTIVE_HEDGE_IQV_RATIO = 0.65       # Max allowed IQV movement deviation before active hedge
HG_PASSIVE_HEDGE_SP_RATIO = 0.003       # Stop-loss offset for passive hedge
HG_PASSIVE_HEDGE_PROPORTION = 0.5      # Hedge proportion of total exposure
HG_PASSIVE_HEDGE_REFRESH_IQV_RATIO = 0.2   # Refresh triggers when IQV movement returns within ± this
HG_PASSIVE_HEDGE_REFRESH_INTERVAL = 30     # Interval (sec) to refresh passive hedge state
HG_DUAL_SIDED_HEDGE = True              # Whether passive hedge is bidirectional

# === Volatility Model Parameters ===
VOL_HIS_PRICE_WINDOW = 1        # Window size for price history (sec)
VOL_HIS_PRICE_WINDOW_LIMIT = 1000  # Max history price size stored
VOL_SHORT_WINDOW = 60             # Short-term window
VOL_LONG_WINDOW = 600             # Long-term window
VOL_EWMA_LAMBDA = 0.94           # EWMA decay factor
