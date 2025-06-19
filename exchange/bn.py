import asyncio
from binance.spot import Spot as BNSpot
from binance.um_futures import UMFutures

from exchange_base import Exchange
from binance_settings import tick_size, step_size

class Binance(Exchange):
    def __init__(self, api_key: str, secret_key: str):
        super().__init__('Binance', api_key, secret_key)
        # Initialize Binance-specific client
        self.spot_client = BNSpot(api_key=self.__key, api_secret=self.__secret)
        self.perp_client = UMFutures(key=self.__key, secret=self.__secret)
    
    async def put_spot_limit_order(self, symbol: str, side: str, quantity: float, price: float, gtx_only: bool = False) -> tuple[bool, str]:
        try:
            symbol = symbol.strip().upper()
            side = side.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'

            quantity = round(quantity, step_size[symbol])
            price = round(price, tick_size[symbol])
            if gtx_only:
                response = self.spot_client.new_order(symbol=symbol, side=side, type='LIMIT_MAKER', quantity=quantity, price=price)
            else:
                response = self.spot_client.new_order(symbol=symbol, side=side, type='LIMIT', quantity=quantity, price=price, timeInForce='GTC')
            order_id = response['orderId']

            return True, str(order_id)
        except Exception as e:
            return False, f'Error met in {self.exchange_name} put_perp_limit_order: {e}' 
    

    async def batch_put_spot_limit_orders(self, symbol: str, orders: list, gtx_only: bool) -> list:
        '''
            Asynchronously batch place spot limit orders.

            Args:
                symbol (str): Trading symbol, e.g., 'BTCUSDT'.
                orders (list): List of orders, each as [side, quantity, price].
                gtx_only (bool): If True, use LIMIT_MAKER to avoid taker trades.

            Returns:
                list: A list of orderIds (str) for successfully placed orders, or None if failed.
        '''
        tasks = [
            self.put_spot_limit_order(
                symbol=symbol,
                side=order[0],
                quantity=order[1],
                price=order[2],
                gtx_only=gtx_only
            )
            for order in orders
        ]

        results = await asyncio.gather(*tasks)
        order_ids = []
        for success, order_id in results:
            if success:
                order_ids.append(order_id)

        return order_ids


    async def batch_query_orders(self, symbol: str, orders: list, limit=100) -> dict:
        '''
            Query multiple spot orders by their order IDs.

            Args:
                symbol (str): Trading symbol, e.g., 'BTCUSDT'.
                orders (list): A list of order IDs to query.

            Returns:
                dict: A dict of order dictionaries for the matching order IDs.
                Item structure is {order_id: (side, size, quote_size)}
            '''
        try:
            all_orders = self.spot_client.get_orders(symbol=symbol, limit=limit)
        except Exception as e:
            print(f'Failed to fetch orders for {symbol}: {e}')
            return dict()

        # Create a lookup dict for quick access by orderId
        order_map = {str(o['orderId']): o for o in all_orders}

        # Match requested orderIds
        result = dict()
        for order_id in orders:
            status = order_map.get(str(order_id))
            if status and float(status['cummulativeQuoteQty']) > 0:
                size = float(status['executedQty'])
                quote_size = float(status['cummulativeQuoteQty'])
                side = status['side']
                result[order_id] = (side, size, quote_size)

        return result

    
    async def cancel_all_spot_orders(self, symbol: str) -> bool:
        try:
            symbol = symbol.strip().upper()
            response = self.spot_client.cancel_open_orders(symbol=symbol)
            if all([order['status']] == 'CANCELED' for order in response):
                return True
            else:
                return False
        except Exception as e:
            print(f'Error met in {self.exchange_name} cancel_all_spot_orders: {e}' )

    async def put_perp_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> str:
        try:
            symbol = symbol.strip().upper()
            side = side.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'

            quantity = round(quantity, step_size[symbol])
            price = round(price, tick_size[symbol])

            response = self.perp_client.new_order(symbol=symbol, side=side, type='LIMIT', quantity=quantity, price=price)
            order_id = response['orderId']

            return str(order_id)
        except Exception as e:
            return f'Error met in {self.exchange_name} put_perp_limit_order: {e}' 
    
    async def put_perp_market_order(self, symbol: str, side: str, quantity: float) -> tuple[bool, float | str]:
        try:
            symbol = symbol.strip().upper()
            side = side.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'

            quantity = round(quantity, step_size[symbol])

            response = self.perp_client.new_order(symbol=symbol, side=side, type='MARKET', quantity=quantity)
            order_id = response['orderId']
            
            order_details = self.perp_client.query_order(symbol=symbol, orderId=order_id)
            avg_price = float(order_details['avgPrice'])

            return True, avg_price
        except Exception as e:
            return False, f'Error met in {self.exchange_name} put_perp_market_order: {e}'
    
    async def put_perp_trigger_order(self, symbol: str, side: str, quantity: float, trigger_price: float) -> str:
        try:
            symbol = symbol.strip().upper()
            side = side.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'

            quantity = round(quantity, step_size[symbol])
            trigger_price = round(trigger_price, tick_size[symbol])

            response = self.perp_client.new_order(symbol=symbol, side=side, type='STOP_MARKET', quantity=quantity, stopPrice=trigger_price)
            order_id = response['orderId']

            return str(order_id)
        except Exception as e:
            return f'Error met in {self.exchange_name} put_perp_trigger_order: {e}' 
    
    async def put_perp_gtx_order(self, symbol: str, side: str, quantity: float, max_try=30) -> tuple[bool, float | str]:
        symbol = symbol.strip().upper()
        side = side.strip().upper()
        assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
        assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'

        quantity = round(quantity, step_size[symbol])
        unfilled_amount = quantity
        try_times = 0
        for _ in range(5):
            try:
                init_positions = [position for position in self.perp_client.account()['positions'] if position['symbol'] == symbol]
                if not init_positions:
                    init_balance = 0
                else:
                    init_balance = float(init_positions[0]['positionAmt'])
                break
            except Exception as e:
                print(f'Fetch init balance met error: {e}, retry')
                await asyncio.sleep(1)
        else:
            print(f'Fetch init balance failed after 5 times, failed GTX {side}.')
            return unfilled_amount
        
        while True:
            try_times += 1
            ob = self.perp_client.depth(symbol)
            if side == 'BUY':
                gtx_price = float(ob['bids'][0][0])
            else:
                gtx_price = float(ob['asks'][0][0])
            print(gtx_price)
            try:
                # send gtx order 
                response = self.perp_client.new_order(symbol=symbol, side=side, type='LIMIT', quantity=unfilled_amount, timeInForce="GTX", price=gtx_price)
                print(response)
                order_id = response['orderId']
                # wait 3 seconds and cancel the order
                await asyncio.sleep(3)
                self.perp_client.cancel_order(symbol=symbol, orderId=order_id)
            except Exception as e:
                print('Send GTX limit order or cancel order failed, sleep 1 second and retry.')
                await asyncio.sleep(1)
            # check current position, update unfilled quantity
            for _ in range(5):
                try:
                    cur_positions = [position for position in self.perp_client.account()['positions'] if position['symbol'] == symbol]
                    if not cur_positions:
                        cur_balance = 0
                    else:
                        cur_balance = float(cur_positions[0]['positionAmt'])
                    if side == 'BUY':
                        unfilled_amount = quantity - (cur_balance - init_balance)
                    else:
                        unfilled_amount = quantity - (init_balance - cur_balance)
                    break
                except Exception as e:
                    print(f'Fetch current balance met error: {e}, retry')
                    await asyncio.sleep(1)
            else:
                print(f'Fetch current balance failed after 5 times, failed GTX {side}.')
                return unfilled_amount

            if unfilled_amount <= 0.000000001:
                print(f'Successfully complete the GTX order after {try_times} tries')
                return True, 0
            else:
                print(f'Complete the {try_times} try, current filled status: {quantity - unfilled_amount}/{quantity}.')
            
            await asyncio.sleep(1)

            if try_times >= max_try:
                print(f'Failed to fill the GTX order after {max_try} tries, current filled status: {quantity - unfilled_amount}/{quantity}.')
                return unfilled_amount

        # todo: Calculate GTX average filled price
    
    def query_perp_order_status(self, symbol: str, orderId: int) -> dict:
        try:
            order_status = self.perp_client.query_order(symbol=symbol, orderId=orderId)
            return order_status
        except Exception as e:
            print(f'Query Order {orderId} status met error: {e}.')
    
    def cancel_perp_order(self, symbol: str, orderId: int) -> bool:
        try:
            order_status = self.perp_client.cancel_order(symbol=symbol, orderId=orderId)
            is_canceled = True if order_status['status'] == 'CANCELED' else False
            return is_canceled
        except Exception as e:
            print(f'Cancel Order {orderId} met error: {e}.')
        


    








    


    

    