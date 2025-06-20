import sys
import os
import asyncio
from collections import deque
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feeds.historical import bn_klines_close_price
from feeds.live import BnFeedsConnector, HypeFeedsConnector
from strategies import Spot, Curve, BidAsk, AutoMode, VolatilityEstimator
from exchange import BN, Hyperliquid
from hedge.hedge import Hedge
from configs.auth import *
from init_config import validate_and_load_config
from log_config import setup_logger, color_log

class MarketMakerRunner():
    def __init__(self, 
                 underlying_token: str,
                 quote_token: str,
                 marketplace: str,
                 hedge_marketplace: str,
                 mm_update_interval: int,
                 mm_price_up_pct_limit: float,
                 mm_price_down_pct_limit: float,
                 mm_bin_step: int, 
                 mm_init_inventory_amount: float,
                 mm_init_quote_amount: float,
                 mm_mode: str,
                 mm_live_order_nums: int,
                 mm_min_order_size: float,
                 mm_max_order_size: float,
                 mm_iqv_up_limit: float,
                 mm_iqv_down_limit: float,
                 mm_inventory_rb_iqv_ratio: float,
                 mm_quote_rb_iqv_ratio: float,
                 auto_mm_vol_lower_threshold: float,
                 auto_mm_vol_upper_threshold: float,
                 hg_passive_hedge_ratio: float,
                 hg_min_hedge_order_size: float,
                 hg_active_hedge_iqv_ratio: float,
                 hg_passive_hedge_sp_ratio: float,
                 hg_passive_hedge_proportion: float,
                 hg_passive_hedge_refresh_iqv_ratio: float,
                 hg_passive_hedge_refresh_interval: int,
                 hg_dual_sided_hedge: bool,
                 vol_his_price_window: int,
                 vol_his_price_window_limit: int,
                 vol_short_window: int,
                 vol_long_window: int,
                 vol_ewma_lambda: float,
                 ) -> None:

        self.token = underlying_token.strip().upper()
        self.quote = quote_token.strip().upper()
        self.marketplace = marketplace.strip().lower()
        self.hedge_marketplace = hedge_marketplace.strip().lower()

        if marketplace == 'binance_spot':
            self.symbol = f'{underlying_token}{quote_token}'
            self.hedge_symbol = self.symbol
            self.feed = BnFeedsConnector(self.symbol)
        elif marketplace == 'hyperliquid':
            self.symbol = self.token
            self.hedge_symbol = f'{underlying_token}{quote_token}'
            self.feed = HypeFeedsConnector(self.symbol)
        else:
            raise NotImplementedError
        
        self.mm_update_interval = mm_update_interval
        self.mm_price_up_pct_limit = mm_price_up_pct_limit
        self.mm_price_down_pct_limit = mm_price_down_pct_limit
        self.mm_bin_step = mm_bin_step
        self.mm_init_inventory_amount = mm_init_inventory_amount
        self.mm_init_quote_amount = mm_init_quote_amount
        self.mm_live_order_nums = mm_live_order_nums
        self.mm_min_order_size = mm_min_order_size
        self.mm_max_order_size = mm_max_order_size
        self.mm_iqv_up_limit = mm_iqv_up_limit
        self.mm_iqv_down_limit = mm_iqv_down_limit
        self.mm_inventory_rb_iqv_ratio = mm_inventory_rb_iqv_ratio
        self.mm_quote_rb_iqv_ratio = mm_quote_rb_iqv_ratio
        self.mm_mode = mm_mode.strip().lower()
        self.auto_mm_vol_lower_threshold = auto_mm_vol_lower_threshold
        self.auto_mm_vol_upper_threshold = auto_mm_vol_upper_threshold

        self.hg_passive_hedge_ratio = hg_passive_hedge_ratio
        self.hg_min_hedge_order_size = hg_min_hedge_order_size
        self.hg_active_hedge_iqv_ratio = hg_active_hedge_iqv_ratio
        self.hg_passive_hedge_sp_ratio = hg_passive_hedge_sp_ratio
        self.hg_passive_hedge_proportion = hg_passive_hedge_proportion
        self.hg_passive_hedge_refresh_iqv_ratio = hg_passive_hedge_refresh_iqv_ratio
        self.hg_passive_hedge_refresh_interval = hg_passive_hedge_refresh_interval
        self.hg_dual_sided_hedge = hg_dual_sided_hedge
        
        self.vol_his_price_window = vol_his_price_window
        self.vol_his_price_window_limit = vol_his_price_window_limit
        self.vol_his_price = deque(maxlen=vol_his_price_window_limit)
        self.vol_short_window = vol_short_window
        self.vol_long_window = vol_long_window
        self.vol_ewma_lambda = vol_ewma_lambda

        self.ex_client = None
        self.hedge_ex_client = None
        self.mm_client = None
        self.hedge_client = None 
        self.vol_client = None
        self.vol = None
        self.inventory_amount = mm_init_inventory_amount
        self.quote_amount = mm_init_quote_amount
        self.iqv_move_ratio = None

        self.oids = [] # OrderIds list

        self.is_closed = False

        color_log('info', 'Start Running MarketMaker Runner.')

    
    async def live_price_monitor(self):
        _tasks = [
            asyncio.create_task(self.feed.monitor_spot()),
            asyncio.create_task(self.feed.monitor_top_depth())
        ]
        await asyncio.gather(*_tasks)


    
    @property
    def mid_price(self):
        depth = self.feed.top_depth
        if depth:
            mid_price = (float(depth['bids'][0][0]) + float(depth['asks'][0][0])) / 2
            return mid_price
    
    @property
    def aggr_price(self):
        aggr_price = self.feed.spot_price
        if aggr_price:
            return aggr_price
    
    def price_security_check(self) -> bool:
        if not self.aggr_price or not self.mid_price:
            return False
        if abs((self.aggr_price - self.mid_price) / self.mid_price) < 0.02:
            return True
        else:
            return False
    
    async def initialize_clients(self) -> bool:
            while not self.mid_price or not self.aggr_price:
                await asyncio.sleep(1)
            retry = 10
            while True:
                if self.ex_client == None:
                    if self.marketplace == 'binance_spot':
                        self.ex_client = BN(api_key=bn_api_key, secret_key=bn_secret_key)
                        color_log('info', 'Successfully initialized Market-Maker Binance-Spot Trade Client.')
                    elif self.marketplace == 'hyperliquid':
                        self.ex_client = Hyperliquid(api_key=hype_pub_key, secret_key=hype_pri_key)
                        color_log('info', 'Successfully initialized Market-Maker Hyperliquid Trade Client.')
                    else:
                        raise NotImplementedError
                if self.hedge_ex_client == None:
                    if self.hedge_marketplace == 'binance_perp':
                        self.hedge_ex_client = BN(api_key=bn_api_key, secret_key=bn_secret_key)
                        color_log('info', 'Successfully initialized Hedge Trade Client.')
                    else:
                        raise NotImplementedError
                if self.vol_client == None:
                    self.vol_client = VolatilityEstimator(short_window=self.vol_short_window, long_window=self.vol_long_window, ewma_lambda=self.vol_ewma_lambda)
                    color_log('info', 'Successfully initialized Volatility Estimator Client.')
                if self.mm_client == None:
                    if self.mid_price and self.price_security_check():
                        if self.mm_mode == 'spot':
                            self.mm_client = Spot(underlying_asset=self.token, quote_asset=self.quote, init_price=self.mid_price, 
                                                  price_up_pct_limit=self.mm_price_up_pct_limit, price_down_pct_limit=self.mm_price_down_pct_limit, 
                                                  bin_step=self.mm_bin_step, init_inventory_amount=self.mm_init_inventory_amount, 
                                                  init_quote_amount=self.mm_init_quote_amount, live_order_nums=self.mm_live_order_nums,
                                                  min_order_size=self.mm_min_order_size, max_order_size=self.mm_max_order_size,
                                                  iqv_up_limit=self.mm_iqv_up_limit, iqv_down_limit=self.mm_iqv_down_limit,
                                                  inventory_rb_iqv_ratio=self.mm_inventory_rb_iqv_ratio, quote_rb_iqv_ratio=self.mm_quote_rb_iqv_ratio)
                            color_log('info', 'Successfully initialized Spot-Mode Market-Maker Client.')
                        elif self.mm_mode == 'curve':
                            self.mm_client = Curve(underlying_asset=self.token, quote_asset=self.quote, init_price=self.mid_price, 
                                                  price_up_pct_limit=self.mm_price_up_pct_limit, price_down_pct_limit=self.mm_price_down_pct_limit, 
                                                  bin_step=self.mm_bin_step, init_inventory_amount=self.mm_init_inventory_amount, 
                                                  init_quote_amount=self.mm_init_quote_amount, live_order_nums=self.mm_live_order_nums,
                                                  min_order_size=self.mm_min_order_size, max_order_size=self.mm_max_order_size,
                                                  iqv_up_limit=self.mm_iqv_up_limit, iqv_down_limit=self.mm_iqv_down_limit,
                                                  inventory_rb_iqv_ratio=self.mm_inventory_rb_iqv_ratio, quote_rb_iqv_ratio=self.mm_quote_rb_iqv_ratio)
                            color_log('info', 'Successfully initialized Curve-Mode Market-Maker Client.')
                        elif self.mm_mode == 'bid_ask':
                            self.mm_client = BidAsk(underlying_asset=self.token, quote_asset=self.quote, init_price=self.mid_price, 
                                                  price_up_pct_limit=self.mm_price_up_pct_limit, price_down_pct_limit=self.mm_price_down_pct_limit, 
                                                  bin_step=self.mm_bin_step, init_inventory_amount=self.mm_init_inventory_amount, 
                                                  init_quote_amount=self.mm_init_quote_amount, live_order_nums=self.mm_live_order_nums,
                                                  min_order_size=self.mm_min_order_size, max_order_size=self.mm_max_order_size,
                                                  iqv_up_limit=self.mm_iqv_up_limit, iqv_down_limit=self.mm_iqv_down_limit,
                                                  inventory_rb_iqv_ratio=self.mm_inventory_rb_iqv_ratio, quote_rb_iqv_ratio=self.mm_quote_rb_iqv_ratio)
                            color_log('info', 'Successfully initialized BidAsk-Mode Market-Maker Client.')
                        elif self.mm_mode == 'auto':
                            self.mm_client = AutoMode(underlying_asset=self.token, quote_asset=self.quote, init_price=self.mid_price, 
                                                  price_up_pct_limit=self.mm_price_up_pct_limit, price_down_pct_limit=self.mm_price_down_pct_limit, 
                                                  bin_step=self.mm_bin_step, init_inventory_amount=self.mm_init_inventory_amount, 
                                                  init_quote_amount=self.mm_init_quote_amount, live_order_nums=self.mm_live_order_nums,
                                                  min_order_size=self.mm_min_order_size, max_order_size=self.mm_max_order_size,
                                                  iqv_up_limit=self.mm_iqv_up_limit, iqv_down_limit=self.mm_iqv_down_limit,
                                                  inventory_rb_iqv_ratio=self.mm_inventory_rb_iqv_ratio, quote_rb_iqv_ratio=self.mm_quote_rb_iqv_ratio,
                                                  vol_lower_threshold=self.auto_mm_vol_lower_threshold, vol_upper_threshold=self.auto_mm_vol_upper_threshold,
                                                  init_vol=(self.auto_mm_vol_lower_threshold + self.auto_mm_vol_upper_threshold) / 2)
                            color_log('info', 'Successfully initialized Auto-Mode Market-Maker Client.')
                        else:
                            raise NotImplementedError
                if self.hedge_client == None:
                    if self.aggr_price and self.price_security_check():
                        self.hedge_client = Hedge(exchange_client=self.hedge_ex_client, symbol=self.hedge_symbol, init_price=self.aggr_price, 
                                                passive_hedge_ratio=self.hg_passive_hedge_ratio, init_inventory_amount=self.mm_init_inventory_amount,
                                                init_quote_amount=self.mm_init_quote_amount, min_hedge_order_size=self.hg_min_hedge_order_size,
                                                active_hedge_iqv_ratio=self.hg_active_hedge_iqv_ratio, passive_hedge_sp_ratio=self.hg_passive_hedge_sp_ratio,
                                                passive_hedge_proportion=self.hg_passive_hedge_proportion, passive_hedge_refresh_iqv_ratio=self.hg_passive_hedge_refresh_iqv_ratio,
                                                passive_hedge_refresh_interval=self.hg_passive_hedge_refresh_interval, dual_sided_hedge=self.hg_dual_sided_hedge)
                        color_log('info', 'Successfully initialized Hedge Client.')

                if all([self.ex_client, self.hedge_ex_client, self.vol_client, self.mm_client, self.hedge_client]):
                    color_log('info', 'Initialize All Clients Success.')
                    break
                else:
                    retry -= 1
                    await asyncio.sleep(5)     
    
    async def vol_monitor(self):
        pass_windows = bn_klines_close_price(symbol=self.hedge_symbol, interval=self.vol_his_price_window, limit=self.vol_his_price_window_limit)
        self.vol_his_price.extend(pass_windows)
        await asyncio.sleep(self.vol_his_price_window)
        i = 0
        while not self.is_closed:
            if self.price_security_check():
                self.vol_his_price.append(self.aggr_price)
                self.vol_client.update(self.vol_his_price)
                self.vol = self.vol_client.vol
                if self.mm_mode == 'auto':
                    self.mm_client.update_vol(self.vol)
                if i % 120 == 0: 
                    color_log('market', f'Current Price: {self.aggr_price}, Current Effective Volatility: {self.vol}')
                i += 1

            await asyncio.sleep(self.vol_his_price_window)
    
    async def mm(self):
        round_index = 0
        while not self.is_closed:
            # Step 1, Cancel current orders if exists
            if self.marketplace == 'binance_spot':
                await self.ex_client.cancel_all_spot_orders(symbol=self.symbol)
            elif self.marketplace == 'hyperliquid':
                await self.ex_client.batch_cancel_orders(symbol=self.symbol, oids=self.oids)
            else:
                raise NotImplementedError
            # Step 2, Query all orders information if exists
            if len(self.oids) > 0:
                if self.marketplace == 'binance_spot':
                    filled_status = await self.ex_client.batch_query_orders(symbol=self.symbol, orders=self.oids, limit=max(100, self.mm_live_order_nums))
                elif self.marketplace == 'hyperliquid':
                    filled_status = await self.ex_client.batch_query_orders(symbol=self.symbol, orders=self.oids, query_start_time=7200)
                else:
                    raise NotImplementedError
            # Step 3, Calculate current mm round position updates from filled orders
                if len(filled_status) > 0:
                    ic = qc = 0
                    for _, order_info in filled_status.items():
                        side, size, quote_size = order_info
                        if side == 'BUY':
                            ic += size
                            qc -= quote_size
                        else:
                            ic -= size
                            qc += quote_size
            # Step 4, Summary current round position updates
                    self.inventory_amount += ic
                    self.quote_amount += qc
                    round_avg_price = abs(qc / ic) if abs(ic) > 0 else 0
                    if ic > 0:
                        color_log('success', f'Round {round_index}: Buy {ic} {self.token} with Average Price: {round_avg_price}, Current Inventory Amount: {self.inventory_amount}, Current Quote Amount: {self.quote_amount}')
                    elif ic < 0:
                        color_log('success', f'Round {round_index}: Sell {ic} {self.token} with Average Price: {round_avg_price}, Current Inventory Amount: {self.inventory_amount}, Current Quote Amount: {self.quote_amount}')
                    else:
                        color_log('success', f'Round {round_index}: No Inventory Changes, Current Inventory Amount: {self.inventory_amount}, Current Quote Amount: {self.quote_amount}')
                else:
                    color_log('status', f'Round {round_index}: No Executed Orders, Current Inventory Amount: {self.inventory_amount}, Current Quote Amount: {self.quote_amount}')
            # Step 5, Compute latest bins based on current position and volatility
            self.mm_client.compute_current_bins(current_price=self.mid_price, cur_inventory_amount=self.inventory_amount, cur_quote_amount=self.quote_amount)   
            self.iqv_move_ratio = self.mm_client.iqv_move_ratio
            self.hedge_client.update_portfolio_status(current_price=self.aggr_price, cur_inventory_amount=self.inventory_amount, 
                                                      cur_quote_amount=self.quote_amount, iqv_move_ratio=self.iqv_move_ratio)
            bins = self.mm_client.bins
            # print(bins)
            # Step 6, Generate next round orders and batch send
            nr_orders = []
            for ask_bin, bid_bin in zip(bins['asks'], bins['bids']):
                ask_price, ask_size = ask_bin
                bid_price, bid_size = bid_bin

                nr_orders.append(['SELL', ask_size, ask_price])
                nr_orders.append(['BUY', bid_size, bid_price])

                if len(nr_orders) >= self.mm_live_order_nums:
                    break
            if self.marketplace == 'binance_spot':
                self.oids = await self.ex_client.batch_put_spot_limit_orders(symbol=self.symbol, orders=nr_orders, gtx_only=True)
            elif self.marketplace == 'hyperliquid':
                self.oids = await self.ex_client.batch_put_limit_orders(symbol=self.symbol, orders=nr_orders, gtx_only=True)
            else:
                raise NotImplementedError
            round_index += 1
            
            await asyncio.sleep(self.mm_update_interval)

    async def main(self):
        live_price_task = asyncio.create_task(self.live_price_monitor())
        await asyncio.sleep(1) 
        
        try:
            await self.initialize_clients()
        except Exception as e:
            color_log('error', f"Failed to initialize clients: {e}")
            return
        
        _tasks = [
            live_price_task,  
            asyncio.create_task(self.vol_monitor()),
            asyncio.create_task(self.mm()),
            asyncio.create_task(self.hedge_client.passive_hedge_monitor()),
            asyncio.create_task(self.hedge_client.active_hedge_monitor()),
        ]
        await asyncio.gather(*_tasks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Start MarketMaker Runner with provided config file.")
    parser.add_argument("--config_file", "-c", required=True, help="Name of the config .py file in [MM/configs/]")
    parser.add_argument("--log_file", "-l", default="./tracks/mm.log", help="Path to the log file (default: ./tracks/mm.log)"
)
    args = parser.parse_args()

    setup_logger(args.log_file)

    cfg = validate_and_load_config(args.config_file)

    runner = MarketMakerRunner(
                underlying_token=cfg['underlying_token'],
                quote_token=cfg['quote_token'],
                marketplace=cfg['marketplace'],
                hedge_marketplace=cfg['hedge_marketplace'],
                mm_update_interval=cfg['mm_update_interval'],
                mm_price_up_pct_limit=cfg['mm_price_up_pct_limit'],
                mm_price_down_pct_limit=cfg['mm_price_down_pct_limit'],
                mm_bin_step=cfg['mm_bin_step'],
                mm_init_inventory_amount=cfg['mm_init_inventory_amount'],
                mm_init_quote_amount=cfg['mm_init_quote_amount'],
                mm_mode=cfg['mm_mode'],
                mm_live_order_nums=cfg['mm_live_order_nums'],
                mm_min_order_size=cfg['mm_min_order_size'],
                mm_max_order_size=cfg['mm_max_order_size'],
                mm_iqv_up_limit=cfg['mm_iqv_up_limit'],
                mm_iqv_down_limit=cfg['mm_iqv_down_limit'],
                mm_inventory_rb_iqv_ratio=cfg['mm_inventory_rb_iqv_ratio'],
                mm_quote_rb_iqv_ratio=cfg['mm_quote_rb_iqv_ratio'],
                auto_mm_vol_lower_threshold=cfg['auto_mm_vol_lower_threshold'],
                auto_mm_vol_upper_threshold=cfg['auto_mm_vol_upper_threshold'],
                hg_passive_hedge_ratio=cfg['hg_passive_hedge_ratio'],
                hg_min_hedge_order_size=cfg['hg_min_hedge_order_size'],
                hg_active_hedge_iqv_ratio=cfg['hg_active_hedge_iqv_ratio'],
                hg_passive_hedge_sp_ratio=cfg['hg_passive_hedge_sp_ratio'],
                hg_passive_hedge_proportion=cfg['hg_passive_hedge_proportion'],
                hg_passive_hedge_refresh_iqv_ratio=cfg['hg_passive_hedge_refresh_iqv_ratio'],
                hg_passive_hedge_refresh_interval=cfg['hg_passive_hedge_refresh_interval'],
                hg_dual_sided_hedge=cfg['hg_dual_sided_hedge'],
                vol_his_price_window=cfg['vol_his_price_window'],
                vol_his_price_window_limit=cfg['vol_his_price_window_limit'],
                vol_short_window=cfg['vol_short_window'],
                vol_long_window=cfg['vol_long_window'],
                vol_ewma_lambda=cfg['vol_ewma_lambda']
            )
    asyncio.run(runner.main())   





