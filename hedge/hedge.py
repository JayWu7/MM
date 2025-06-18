import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class Hedge():
    def __init__(self,
                 exchange_client,
                 symbol: str,
                 init_price: float,
                 passive_hedge_ratio: float, # Trigger order in two sides, autolatically hedge when there is a price crash
                 init_inventory_amount: float,
                 init_quote_amount: float,
                 min_hedge_order_size: float,
                 active_hedge_iqv_ratio: float = 0.7, 
                 passive_hedge_sp_ratio: float = 0.005,
                 passive_hedge_proportion: float = 0.5,
                 passive_hedge_refresh_iqv_ratio: float = 0.2,
                 passive_hedge_refresh_interval: int = 30,
                 dual_sided_hedge: bool = True, 
                 ) -> None:
        '''
            A class to manage both active and passive hedging strategies 
            for a crypto trading position based on inventory and market conditions.

            Supports two types of hedge:
            - Active hedge: automatically reduce/increase inventory size when the inventory/quote exposure exceeds a given threshold.
            - Passive hedge: triggered automatically on both sides when price crashes or volatility spikes.

            Parameters:
            -----------
                exchange_client : Exchange 
                    Exchange interface for placing hedge orders, e.g., Binance or OKX client.
                
                symbol : str 
                    The trading pair symbol, e.g., 'BTCUSDT'.
                
                init_price : float
                    The starting price used to calculate initial inventory value.
                
                active_hedge_ratio : float
                    Ratio threshold at which an active hedge will be triggered, 
                    based on inventory exposure changes.
                
                init_inventory_amount : float
                    Initial amount of base asset held (e.g., 0.5 BTC).
                
                init_quote_amount : float
                    Initial amount of quote currency held (e.g., 20,000 USDT).
                
                min_hedge_order_size : float: 
                    Minimum allowable size for a hedge order. 
                
                active_hedge_iqv_ratio : float: 
                    threshold (relative change) for trigger active hedging. 
                    When IQV movement exceeds this ratio upward, begining actively adjust inventory size.

                passive_hedge_sp_ratio : float 
                    Passive hedge position stop-loss ratio

                passive_hedge_proportion : float, optional: 
                    The proportion of the maximum inventory exposure risk to be hedged passively. 
                    Default is 0.5 (50% of maximum inventory exposure).
                
                passive_hedge_update_iqv_ratio : float:  
                    Threshold of inventory quote value (IQV) movement for refreshing passive hedge trigger prices.
                
                passive_hedge_refresh_interval : int:
                    Time interval (in seconds) for checking and refreshing passive hedge trigger prices.
                
                dual_sided_hedge : bool: 
                    Specifies whether the hedging is **unilateral** or **bilateral**.

                    - `False`: Only hedge against downside price risk (i.e., inventory value dropping).  

                    - `True`: Hedge both downside and upside price movements to prevent large 
                    impermanent loss
        '''
        
        self.symbol = symbol
        self.passive_hedge_ratio = passive_hedge_ratio
        self.passive_hedge_sp_ratio = passive_hedge_sp_ratio
        self.price = init_price
        self.min_hedge_order_size = min_hedge_order_size
        self.cur_inventory_amount = init_inventory_amount
        self.cur_inventory_value = init_inventory_amount * init_price
        self.cur_quote_amount = init_quote_amount
        self.init_iqv_ratio = init_inventory_amount * init_price / (init_inventory_amount * init_price + init_quote_amount)
        self.iqv_ratio = self.init_iqv_ratio # inventory value / (inventory value + quote value)
        self.iqv_move_ratio = 0 # (iqv_ratio - init_iqv_ratio) / init_iqv_ratio
        self.active_hedge_iqv_ratio = active_hedge_iqv_ratio
        self.passive_hedge_proportion = passive_hedge_proportion
        self.passive_hedge_refresh_iqv_ratio = passive_hedge_refresh_iqv_ratio
        self.passive_hedge_refresh_interval = passive_hedge_refresh_interval

        self.dual_sided_hedge = dual_sided_hedge

        self.active_hedge_size = 0
        self.passive_hedge_size = 0
        self.p_hedge_long_trigger_price = self.p_hedge_short_trigger_price = 0
        self.passive_hedge_long_orderId = self.passive_hedge_short_orderId = self.passive_hedge_sp_orderId = None
        

        self.is_hedge_live = True
        self.is_on_p_hedge = False

        self.trade_client = exchange_client.perp_client
    

    def update_portfolio_status(self, current_price: float, cur_inventory_amount: float, cur_quote_amount: float, iqv_move_ratio: float) -> None:
        # Update price
        self.price = current_price
        # Update asset quantities
        self.cur_inventory_amount = cur_inventory_amount
        self.cur_quote_amount = cur_quote_amount
        # Update iqv_move_ratio
        self.iqv_move_ratio = iqv_move_ratio


    async def active_hedge_monitor(self) -> None:
        try:
            while self.is_hedge_live:
                if self.iqv_move_ratio > self.active_hedge_iqv_ratio: # Need to reduce inventory (short)
                    '''
                        Short Hedge Size Calculation Logic:
                        We aim to reduce the inventory to bring the IQV (Inventory Quote Value ratio)
                        back to the target level (init_iqv_ratio ± active_hedge_iqv_ratio).
                        
                        Let x be the amount of inventory to sell (hedge size).
                        
                        After selling x:
                        - Inventory becomes (cur_inventory_amount - x)
                        - Quote balance increases by (x * price)
                        
                        The new IQV is:
                            ((cur_inventory_amount - x) * price) /
                            [ (cur_inventory_amount - x) * price + cur_quote_amount + x * price ]
                        
                        Solve for x such that:
                            new IQV / init_iqv_ratio = active_hedge_iqv_ratio
                    '''
                    i = self.cur_inventory_amount
                    p = self.price
                    N = self.init_iqv_ratio * self.active_hedge_iqv_ratio
                    q = self.cur_quote_amount

                    x = (i * p - N * i * q -  N * q) / p
                    assert x > 0, 'Calculate Active Hedge Size met error.'
                    _cur_active_hedge_size = - x
                    _execute_size = _cur_active_hedge_size - self.active_hedge_size
                elif self.iqv_move_ratio < -self.active_hedge_iqv_ratio and self.hedge_side == 'two-way': # Need to increase inventory (long)
                    '''
                        Long Hedge Size Calculation Logic:
                        We aim to increase the inventory to bring the IQV (Inventory Quote Value ratio)
                        back to the target level (init_iqv_ratio ± active_hedge_iqv_ratio).
                        
                        Let x be the amount of inventory to buy (hedge size).
                        
                        After buying x:
                        - Inventory becomes (cur_inventory_amount + x)
                        - Quote balance decreases by (x * price)
                        
                        The new IQV is:
                            ((cur_inventory_amount + x) * price) /
                            [ (cur_inventory_amount + x) * price + cur_quote_amount - x * price ]
                        
                        Solve for x such that:
                            new IQV / init_iqv_ratio = active_hedge_iqv_ratio
                    '''
                    i = self.cur_inventory_amount
                    p = self.price
                    N = self.init_iqv_ratio * self.active_hedge_iqv_ratio
                    q = self.cur_quote_amount

                    x = (N * i * q + N * q - i * p) / p
                    assert x > 0, 'Calculate Active Hedge Size met error.'
                    _cur_active_hedge_size = x       
                    _execute_size = _cur_active_hedge_size - self.active_hedge_size           
                else:
                    _cur_active_hedge_size = 0
                    _execute_size = 0

                # Execute Hedge Orders
                if abs(_execute_size) > self.min_hedge_order_size: # Execute gtx long order
                    unfilled_amount = await self.trade_client.put_perp_gtx_order(self.symbol, 'BUY' if _execute_size > 0 else 'SELL', _execute_size)
                    if unfilled_amount > 0:
                        await self.trade_client.put_perp_market_order(self.symbol, 'BUY' if _execute_size > 0 else 'SELL', _execute_size)
                
                self.active_hedge_size = _execute_size
                await asyncio.sleep(1)

        except Exception as e:
            print(f"Active Hedge Monitor Error: {e}")
    

    async def passive_hedge_monitor(self) -> None:
        '''
            Monitors and manages passive hedge orders based on IQV ratio and trigger order status.

            - If not currently in a passive hedge position:
                - Monitors trigger orders (long and/or short depending on `dual_sided_hedge`).
                - If a trigger order is filled, places a corresponding stop-loss (exit) order.
                - If the IQV movement ratio returns to a neutral range (±passive_hedge_update_iqv_ratio), 
                updates hedge trigger prices based on the current market price, and cancels + re-places both long and short trigger orders accordingly.
                - Ensures that long and/or short trigger orders are always placed depending on `dual_sided_hedge`.
            - If currently in a passive hedge position:
                - Monitors the corresponding stop-loss order.
                - Once filled, resets state and re-enables passive hedging.

            - Supports one-way or two-way hedging via the `dual_sided_hedge` parameter.
            - Executes the check every `passive_hedge_refresh_interval` seconds.
        '''
        try:
            while self.is_hedge_live:
                if not self.is_on_p_hedge:
                    # Check Ticker Orders Status:
                    if self.dual_sided_hedge and self.passive_hedge_long_orderId:
                        _long_to_status = self.trade_client.query_perp_order_status(self.symbol, int(self.passive_hedge_long_orderId))
                        if _long_to_status['status'] == 'FILLED':
                            _filled_price = float(_long_to_status['avgPrice'])
                            assert self.passive_hedge_size == float(_long_to_status['executedQty']), 'Quantity Error in Passive Hedge Long Trigger Order'
                            self.is_on_p_hedge = True
                            self.passive_hedge_long_orderId = None
                            _ph_sp_price = _filled_price * (1 - self.passive_hedge_sp_ratio)
                            self.passive_hedge_sp_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'SELL', self.passive_hedge_size, _ph_sp_price)
                            print(f'Passive Hedge Long Trigger Order Filled, entry price: {_filled_price}, size: {self.passive_hedge_size}.')
                            print(f'Successfully Sent Passive Hedge Stop-Loss Order, orderId: {self.passive_hedge_sp_orderId}')
                            continue
                        
                    if self.passive_hedge_short_orderId:
                        _short_to_status = self.trade_client.query_perp_order_status(self.symbol, int(self.passive_hedge_short_orderId))
                        if _short_to_status['status'] == 'FILLED':
                            _filled_price = float(_short_to_status['avgPrice'])
                            assert self.passive_hedge_size == float(_short_to_status['executedQty']), 'Quantity Error in Passive Hedge Short Trigger Order'
                            self.is_on_p_hedge = True
                            self.passive_hedge_short_orderId = None
                            _ph_sp_price = _filled_price * (1 + self.passive_hedge_sp_ratio)
                            self.passive_hedge_sp_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'BUY', self.passive_hedge_size, _ph_sp_price)
                            print(f'Passive Hedge Short Trigger Order Filled, entry price: {_filled_price}, size: {self.passive_hedge_size}.')
                            print(f'Successfully Sent Passive Hedge Stop-Loss Order, orderId: {self.passive_hedge_sp_orderId}')
                            continue

                    if -self.passive_hedge_refresh_iqv_ratio <= self.iqv_move_ratio <= self.passive_hedge_refresh_iqv_ratio:      
                        self.p_hedge_long_trigger_price = self.price * (1 + self.passive_hedge_ratio)
                        self.p_hedge_short_trigger_price = self.price * (1 - self.passive_hedge_ratio)           
                        self.passive_hedge_size = self.cur_inventory_amount * self.passive_hedge_proportion

                        if self.passive_hedge_long_orderId: assert self.trade_client.cancel_perp_order(self.symbol, self.passive_hedge_long_orderId), f'Cancel Long Trigger Order: {self.passive_hedge_long_orderId} failed.'
                        if self.passive_hedge_short_orderId: assert self.trade_client.cancel_perp_order(self.symbol, self.passive_hedge_short_orderId), f'Cancel Short Trigger Order: {self.passive_hedge_short_orderId} failed.'

                        if self.dual_sided_hedge:
                            self.passive_hedge_long_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'BUY', self.passive_hedge_size, self.p_hedge_long_trigger_price)
                        self.passive_hedge_short_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'SELL', self.passive_hedge_size, self.p_hedge_short_trigger_price)
                    elif self.dual_sided_hedge and not self.passive_hedge_long_orderId:
                        self.passive_hedge_long_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'BUY', self.passive_hedge_size, self.p_hedge_long_trigger_price)
                    elif not self.passive_hedge_short_orderId:
                        self.passive_hedge_short_orderId = await self.trade_client.put_perp_trigger_order(self.symbol, 'SELL', self.passive_hedge_size, self.p_hedge_short_trigger_price)
                else:
                    _sp_status = self.trade_client.query_perp_order_status(self.symbol, int(self.passive_hedge_sp_orderId))
                    if _sp_status['status'] == 'FILLED':
                        _filled_price = float(_sp_status['avgPrice'])
                        assert self.passive_hedge_size == float(_sp_status['executedQty']), 'Quantity Error in Passive Hedge Stop-Loss Order'
                        self.is_on_p_hedge = False
                        self.passive_hedge_sp_orderId = None
                        print(f'Passive Hedge Stop-Loss Order Filled, filled price: {_filled_price}, side: {_sp_status["side"]}, size: {self.passive_hedge_size}.')

                await asyncio.sleep(self.passive_hedge_refresh_interval)

        except Exception as e:
            pass
    



        
    




        




        

        
