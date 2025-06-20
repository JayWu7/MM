from strategy_base import StrategyBase, logger

class AutoMode(StrategyBase):
    def __init__(self, 
                 underlying_asset: str, 
                 quote_asset: str, 
                 init_price: float, 
                 price_up_pct_limit: float,     
                 price_down_pct_limit: float,  
                 bin_step: int, 
                 init_inventory_amount: float, 
                 init_quote_amount: float, 
                 live_order_nums: int = 100, 
                 min_order_size: float = 0, 
                 max_order_size: float = 1e18, 
                 iqv_up_limit: float = 0.6, 
                 iqv_down_limit: float = -0.6, 
                 inventory_rb_iqv_ratio: float = 0.3, 
                 quote_rb_iqv_ratio: float = -0.3,
                 init_vol: float = 10,
                 vol_lower_threshold: float = 5,
                 vol_upper_threshold: float = 20) -> None:
        
        super().__init__(underlying_asset, quote_asset, init_price, price_up_pct_limit, price_down_pct_limit, bin_step, 
                         init_inventory_amount, init_quote_amount, live_order_nums, min_order_size, max_order_size, 
                            iqv_up_limit, iqv_down_limit, inventory_rb_iqv_ratio, quote_rb_iqv_ratio)
        
        self.strategy_name = 'Auto Mode Market-Maker Strategy'
        self.vol_lower_threshold = vol_lower_threshold
        self.vol_upper_threshold = vol_upper_threshold
        self.vol = init_vol
    
    def update_vol(self, vol: float) -> bool:
        self.vol = vol

    def compute_current_bins(self, current_price: float, cur_inventory_amount: float, cur_quote_amount: float, decay_rate=0.95) -> dict:
        '''
        '''
        # Update inventory and price-related internal state
        self.update_inventory_infos(current_price, cur_inventory_amount, cur_quote_amount)

        # Initialize bins
        bid_bins = []
        ask_bins = []

        # Convert bin_step from basis points to multiplier 
        step_ratio = self.bin_step / 10000

        # Risk-adjusted sizing factor
        buy_scaling = self._compute_buy_size_multiplier()
        sell_scaling = self._compute_sell_size_multiplier()

        if self.vol < self.vol_lower_threshold:
            # === Dynamically calculate max size based on available balance ===
            # total decay sum = 1 + r + r^2 + ... + r^(n-1)
            bid_decay_sum = sum(decay_rate ** i for i in range(self.bid_bin_nums))
            ask_decay_sum = sum(decay_rate ** i for i in range(self.ask_bin_nums))

            # Available for buying (quote asset side)
            quote_capacity = self.cur_quote_amount / current_price if current_price > 0 else 0  # convert to base asset
            max_bid_size = quote_capacity / bid_decay_sum if bid_decay_sum > 0 else 0

            # Available for selling (inventory side)
            max_ask_size = self.cur_inventory_amount / ask_decay_sum if ask_decay_sum > 0 else 0

            for i in range(self.bid_bin_nums):
                offset = (i + 1) * step_ratio * current_price
                decay_factor = decay_rate ** i

                bid_price = current_price - offset
                bid_size = max_bid_size * decay_factor * buy_scaling

                bid_size = min(max(bid_size, self.min_order_size), self.max_order_size)

                if bid_size > 0:
                    bid_bins.append((bid_price, bid_size))
                
                if len(bid_bins) >= int(self.live_order_nums / 2):
                    break 
            
            for i in range(self.ask_bin_nums):
                offset = (i + 1) * step_ratio * current_price
                decay_factor = decay_rate ** i

                ask_price = current_price + offset
                ask_size = max_ask_size * decay_factor * sell_scaling

                ask_size = min(max(ask_size, self.min_order_size), self.max_order_size)

                if ask_size > 0:
                    ask_bins.append((ask_price, ask_size))
                
                if len(ask_bins) >= int(self.live_order_nums / 2):
                    break 

            self.bins = {'bids': bid_bins, 'asks': ask_bins}
        elif self.vol > self.vol_upper_threshold:
            epsilon = 1e-6
            step_ratio = self.bin_step / 10000
            # Risk-adjusted sizing factor
            buy_scaling = self._compute_buy_size_multiplier()
            sell_scaling = self._compute_sell_size_multiplier()

            # Compute total weight sum for normalization
            bid_weight_sum = sum(1 / (decay_rate ** (i + 1) + epsilon) for i in range(self.bid_bin_nums))
            ask_weight_sum = sum(1 / (decay_rate ** (i + 1) + epsilon) for i in range(self.ask_bin_nums))

            for i in range(self.bid_bin_nums):
                offset = (i + 1) * step_ratio * current_price

                weight = 1 / (decay_rate ** (i + 1) + epsilon) / bid_weight_sum

                bid_price = current_price - offset
                bid_size = self.cur_quote_amount * weight / bid_price * buy_scaling

                bid_size = min(max(bid_size, self.min_order_size), self.max_order_size)

                if bid_size > 0:
                    bid_bins.append((bid_price, bid_size))
                
                if len(bid_bins) >= int(self.live_order_nums / 2):
                    break 

            for i in range(self.ask_bin_nums):
                offset = (i + 1) * step_ratio * current_price

                weight = 1 / (decay_rate ** (i + 1) + epsilon) / ask_weight_sum

                ask_price = current_price + offset
                ask_size = self.cur_inventory_amount * weight * sell_scaling

                ask_size = min(max(ask_size, self.min_order_size), self.max_order_size)

                if ask_size > 0:
                    ask_bins.append((ask_price, ask_size))
                
                if len(ask_bins) >= int(self.live_order_nums / 2):
                    break 

            self.bins = {'bids': bid_bins, 'asks': ask_bins}
        else:
            # Available for buying (quote asset side)
            quote_capacity = self.cur_quote_amount / current_price if current_price > 0 else 0  # convert to base asset
            base_bid_size = quote_capacity / self.bid_bin_nums

            # Available for selling (inventory side)
            base_ask_size = self.cur_inventory_amount / self.ask_bin_nums

            # Uniform bin allocation
            for i in range(self.bid_bin_nums):
                offset = (i + 1) * step_ratio * current_price

                bid_price = self.mid_price - offset
                bid_size = min(max(base_bid_size * buy_scaling, self.min_order_size), self.max_order_size)

                if bid_size > 0:
                    bid_bins.append((bid_price, bid_size))
                
                if len(bid_bins) >= int(self.live_order_nums / 2):
                    break 
            
            for i in range(self.ask_bin_nums):
                offset = (i + 1) * step_ratio * current_price

                ask_price = self.mid_price + offset
                ask_size = min(max(base_ask_size * sell_scaling, self.min_order_size), self.max_order_size)

                if ask_size > 0:
                    ask_bins.append((ask_price, ask_size))
                
                if len(ask_bins) >= int(self.live_order_nums / 2):
                    break 

            # Update internal bin record
            self.bins = {'bids': bid_bins, 'asks': ask_bins}
        
        return self.bins
