import logging

logger = logging.getLogger(__name__)

class StrategyBase():
    def __init__(self, 
                 underlying_asset: str,
                 quote_asset: str,
                 init_price: float,
                 price_up_pct_limit: float,     # e.g. 0.05 means +5%
                 price_down_pct_limit: float,   # e.g. 0.05 means -5%
                 bin_step: int,                 # in basis points (bps), e.g. 25 means 0.25%
                 init_inventory_amount: float,
                 init_quote_amount: float,
                 live_order_nums: int = 100,
                 min_order_size: float = 0.0,
                 max_order_size: float = 1e18,
                 iqv_up_limit: float = 0.6, 
                 iqv_down_limit: float = -0.6, 
                 inventory_rb_iqv_ratio: float = 0.3, 
                 quote_rb_iqv_ratio: float = -0.3
                 ) -> None:
        '''
            Base class for passive market making strategy.

            Parameters:
            -----------
            underlying_asset : str
                The symbol of the inventory (base) asset used in the trading pair (e.g., 'BTC').

            quote_asset : str
                The symbol of the quote asset used for pricing (e.g., 'USDT').

            init_price : float
                Initial reference price used for inventory valuation.
            
            price_up_pct_limit : float
                Maximum percentage price increase from mid price for placing ask orders (e.g., 0.05 for +5%).

            price_down_pct_limit : float
                Maximum percentage price decrease from mid price for placing bid orders (e.g., 0.05 for -5%).
            
            bin_step : int
                Price increment between order levels, expressed in basis points (bps).
            
            init_inventory_amount : float
                Initial amount of the inventory (base asset).
            
            init_quote_amount : float
                Initial amount of the quote currency (e.g. USDT).
            
            live_order_nums: int = 100,
                Maximum number of live orders the strategy can place at any given time. 
                This limits the total number of active orders across all bins to avoid excessive order book load.

            min_order_size: float = 0.0,
                The minimum order size allowed by the strategy. Orders below this size will not be placed, 
                helping to filter out dust orders or those disallowed by the exchange.

            max_order_size: float = 1e18,
                The maximum order size allowed by the strategy. Orders above this size will be clipped to 
                avoid risk or violation of exchange limits.
            
            iqv_up_limit : float
                Upper threshold for relative IQV movement (as a percentage of init_iqv_ratio).
                If the IQV has increased by more than this ratio from its initial value, stop buying.
                Formula: (iqv_ratio - init_iqv_ratio) / init_iqv_ratio <= iqv_up_limit
            
            iqv_down_limit : float
                Lower threshold for relative IQV movement (as a percentage of init_iqv_ratio).
                If the IQV has decreased by more than this ratio from its initial value, stop selling.
                Formula: (iqv_ratio - init_iqv_ratio) / init_iqv_ratio >= iqv_down_limit
            
            inventory_rb_iqv_ratio : float
                Rebalance threshold (relative change) for reducing buy order size.
                When IQV movement exceeds this ratio upward, begin linearly decreasing buy order size.
            
            quote_rb_iqv_ratio : float
                Rebalance threshold (relative change) for reducing sell order size.
                When IQV movement falls below this ratio, begin linearly decreasing sell order size.
            
        '''
        self.strategy_name = 'Base MM Strategy'
        self.underlying_asset = underlying_asset.strip().upper()
        self.quote_asset = quote_asset.strip().upper()
        self.symbol = self.underlying_asset + self.quote_asset

        self.init_inventory_amount = init_inventory_amount
        self.init_quote_amount = init_quote_amount

        self.init_price = init_price
        self.mid_price = init_price

        self.cur_inventory_amount = init_inventory_amount
        self.cur_inventory_value = init_inventory_amount * init_price
        self.cur_quote_amount = init_quote_amount
        self.init_iqv_ratio = init_inventory_amount * init_price / (init_inventory_amount * init_price + init_quote_amount)
        self.iqv_ratio = self.init_iqv_ratio # inventory value / (inventory value + quote value)
        self.iqv_move_ratio = 0 # (iqv_ratio - init_iqv_ratio) / init_iqv_ratio

        self.price_up_pct_limit = price_up_pct_limit
        self.price_down_pct_limit = price_down_pct_limit
        self.bin_step = bin_step
        
        bin_step_decimal = bin_step / 10000
        self.ask_bin_nums = int(price_up_pct_limit / bin_step_decimal)
        self.bid_bin_nums = int(price_down_pct_limit / bin_step_decimal)
        self.total_bin_nums = self.ask_bin_nums + self.bid_bin_nums

        self.live_order_nums = live_order_nums
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size 
        self.iqv_up_limit = iqv_up_limit
        self.iqv_down_limit = iqv_down_limit
        self.inventory_rb_iqv_ratio = inventory_rb_iqv_ratio
        self.quote_rb_iqv_ratio = quote_rb_iqv_ratio

        self.bins = dict() # {'bids': [(bid-0-price, bid-0-size), ], 'asks': [(ask-0-price, ask-0-size), ]}
        

    def _update_mid_price(self, current_price: float) -> None:
        '''
            Updates the current mid price.

            Parameters:
            -----------
            current_price : float
                The latest observed market price (typically best bid + best ask / 2).
        '''
        if current_price <= 0:
            raise ValueError("Price must be positive.")
        
        self.mid_price = current_price


    def _compute_iqv_ratio(self):
        '''
            Computes the current inventory-to-total-value ratio (IQV ratio)
            and updates both iqv_ratio and iqv_move_ratio.

            IQV ratio = inventory_value / (inventory_value + quote_value)
            IQV move ratio = (iqv_ratio - init_iqv_ratio) / init_iqv_ratio
        '''
        if self.mid_price is None or self.cur_inventory_amount is None or self.cur_quote_amount is None:
            raise ValueError("mid_price, cur_inventory_amount, and cur_quote_amount must be set before computing IQV ratio.")
        
        self.cur_inventory_value = self.cur_inventory_amount * self.mid_price
        quote_value = self.cur_quote_amount

        total_value = self.cur_inventory_value + quote_value
        if total_value == 0:
            self.iqv_ratio = 0
        else:
            self.iqv_ratio = self.cur_inventory_value / total_value

        self.iqv_move_ratio = (self.iqv_ratio - self.init_iqv_ratio) / self.init_iqv_ratio
    

    def update_inventory_infos(self, current_price: float, cur_inventory_amount: float, cur_quote_amount: float) -> None:
        '''
            Update the current inventory and quote asset information, and recalculate related values.

            Parameters
            ----------
            current_price : float
                The current mid price of the trading pair.

            cur_inventory_amount : float
                The current amount of the underlying (inventory) asset held.

            cur_quote_amount : float
                The current amount of quote asset (e.g., USDT) held.
        '''
        # Update price
        self._update_mid_price(current_price)

        # Update asset quantities
        self.cur_inventory_amount = cur_inventory_amount
        self.cur_quote_amount = cur_quote_amount

        # Calculate inventory value and IQV
        self._compute_iqv_ratio()
    

    def _compute_buy_size_multiplier(self) -> float:
        '''
            Adjusts the buy order size based on current IQV movement.
            If iqv_move_ratio exceeds inventory_rb_iqv_ratio, reduce buy size linearly.
            If it exceeds iqv_up_limit, return 0.

            Returns:
            --------
            float
                Factor to scale down the buy order size
        '''
        if self.iqv_move_ratio is None:
            return 1.0

        if self.iqv_move_ratio < self.inventory_rb_iqv_ratio:
            return 1.0
        elif self.iqv_move_ratio >= self.iqv_up_limit:
            return 0.0
        else:
            factor = 1 - (self.iqv_move_ratio - self.inventory_rb_iqv_ratio) / (self.iqv_up_limit - self.inventory_rb_iqv_ratio)
            return factor


    def _compute_sell_size_multiplier(self) -> float:
        '''
            Adjusts the sell order size based on current IQV movement.
            If iqv_move_ratio is below quote_rb_iqv_ratio, reduce sell size linearly.
            If it goes below iqv_down_limit, return 0.

            Returns:
            --------
            float
                Factor to scale down the buy order size
        '''
        if self.iqv_move_ratio is None:
            return 1.0

        if self.iqv_move_ratio > self.quote_rb_iqv_ratio:
            return 1.0
        elif self.iqv_move_ratio <= self.iqv_down_limit:
            return 0.0
        else:
            factor = 1 - (self.quote_rb_iqv_ratio - self.iqv_move_ratio) / (self.quote_rb_iqv_ratio - self.iqv_down_limit)
            return factor


    def compute_current_bins(self, current_price: float, cur_inventory_amount: float, cur_quote_amount: float) -> dict:
        '''
            Compute the current bid and ask order levels (bins) based on the market price and current inventory status.

            This method generates a set of bid and ask price levels around the current price, taking into account
            inventory and quote balances. The function may adjust order sizes or skip bins according to risk controls
            such as IQV limits or rebalance ratios.

            Parameters
            ----------
            current_price : float
                The latest mid-market price of the trading pair.

            cur_inventory_amount : float
                The current amount of the underlying (inventory) asset held.

            cur_quote_amount : float
                The current amount of the quote asset (e.g., USDT) held.

            Returns
            -------
            dict
                A dictionary containing two keys: 'bids' and 'asks'.
                Each is a list of (price, size) tuples representing passive limit orders to place.
                Example:
                {
                    'bids': [(price1, size1), (price2, size2), ...],
                    'asks': [(price1, size1), (price2, size2), ...]
                }
        '''
        raise NotImplementedError

    
