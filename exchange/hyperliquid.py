import time
import logging
import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange as HypeEx
from hyperliquid.info import Info
from hyperliquid.utils.signing import OrderRequest, CancelRequest
from exchange_base import Exchange
from hyperliquid_settings import tick_size, step_size

logger = logging.getLogger(__name__)

class Hyperliquid(Exchange):
    def __init__(self, api_key: str, secret_key: str):
        super().__init__('Hyperliquid', api_key, secret_key)
        account: LocalAccount = eth_account.Account.from_key(self._secret)
        self._key = account.address
        self.perp_client = HypeEx(account, account_address=self._key)
        self.info = Info(skip_ws=True)
    
    async def put_limit_order(self, symbol: str, side: str, quantity: float, price: float, gtx_only: bool = False) -> tuple[bool, str]:
        try:
            symbol = symbol.strip().upper()
            side = side.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'
            
            is_buy = True if side == 'BUY' else False

            quantity = round(quantity, step_size[symbol])
            price = round(price, tick_size[symbol])
            if gtx_only:
                response = self.perp_client.order(name=symbol, is_buy=is_buy, sz=quantity, limit_px=price, order_type={"limit": {"tif": "Alo"}})
            else:
                response = self.perp_client.order(name=symbol, is_buy=is_buy, sz=quantity, limit_px=price, order_type={"limit": {"tif": "Gtc"}})
            
            if response['status'] == 'ok':
                order_id = response['response']['data']['statuses'][0]['resting']['oid']
                return True, str(order_id)
            else:
                return False, f'Error met in {self.exchange_name} put_limit_order'
        except Exception as e:
            return False, f'Error met in {self.exchange_name} put_limit_order: {e}' 
    

    async def batch_put_limit_orders(self, symbol: str, orders: list, gtx_only: bool) -> list:
        '''
            Asynchronously batch place limit orders.

            Args:
                symbol (str): Trading token symbol, e.g., 'BTC'.
                orders (list): List of orders, each as [side, quantity, price].
                gtx_only (bool): If True, use LIMIT_MAKER to avoid taker trades.

            Returns:
                list: A list of orderIds (str) for successfully placed orders, or None if failed.
        '''
        order_ids = []
        try:
            symbol = symbol.strip().upper()
            assert symbol in tick_size and symbol in step_size, 'Symbol Invalid.'
            order_type = order_type={"limit": {"tif": "Alo"}} if gtx_only else {"limit": {"tif": "Gtc"}}
            order_requests = []
            for order in orders:
                side, quantity, price = order
                assert side in ['BUY', 'SELL'], 'Side Invalid, must be BUY or SELL.'
                is_buy = True if side == 'BUY' else False
                quantity = round(quantity, step_size[symbol])
                price = round(price, tick_size[symbol])
                order_requests.append(OrderRequest(
                    coin=symbol,
                    is_buy=is_buy,
                    sz=quantity,
                    limit_px=price,
                    order_type=order_type,
                    reduce_only=False
                ))
            if order_requests:
                response = self.perp_client.bulk_orders(order_requests=order_requests)
                if response['status'] == 'ok':
                    for status in response['response']['data']['statuses']:
                        if 'resting' in status:
                            order_ids.append(str(status['resting']['oid']))
        except Exception as e:
            logger.error(f'Error met in {self.exchange_name} batch_put_limit_order: {e}')
        
        return order_ids
            
    async def batch_query_orders(self, symbol: str, orders: list, query_start_time=7200) -> dict:
        '''
            Query multiple spot orders by their order IDs.

            Args:
                symbol (str): Trading symbol, e.g., 'BTCUSDT'.
                orders (list): A list of order IDs to query.

            Returns:
                dict: A dict of order dictionaries for the matching order IDs.
                Item structure is {order_id: (side, size, quote_size)}
            '''
        result = dict()
        symbol = symbol.strip().upper()
        try:
            all_fills = self.info.user_fills_by_time(address=self._key, start_time=int((time.time()- query_start_time ) * 1000))
            fill_map = {str(o['oid']): o for o in all_fills}
            for order_id in orders:
                status = fill_map.get(str(order_id))
                if status:
                    size = float(status['sz'])
                    price = float(status['px'])
                    quote_size = size * price - float(status['fee'])
                    side = 'BUY' if status['side'] == 'B' else 'SELL'
                    result[order_id] = (side, size, quote_size)
            return result
        except Exception as e:
            logger.error(f'Failed to fetch orders filled info for {symbol}: {e}')
            return result

    async def batch_cancel_orders(self, symbol: str, oids: list) -> bool:
        try:
            symbol = symbol.strip().upper()
            if oids:
                cancel_requests = [CancelRequest(coin=symbol, oid=int(oid)) for oid in oids]
                response = self.perp_client.bulk_cancel(cancel_requests=cancel_requests)
                if response['status'] == 'ok':
                    return True
                else:
                    return False
            else:
                return True
        except Exception as e:
            logger.error(f'Error met in {self.exchange_name} cancel_all_spot_orders: {e}')
            return False