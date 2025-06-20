import json
import asyncio
import logging
from websocket import create_connection
from feeds_base import FeedsConnector

logger = logging.getLogger(__name__)

class HypeFeedsConnector(FeedsConnector):
    def __init__(self, symbol):
        super().__init__(symbol)  
        self.hype_ws_url = 'wss://api.hyperliquid.xyz/ws'

    async def monitor_top_depth(self, level=10):
        assert level in [5, 10, 20], 'The top level must be 5, 10 or 20.'
        retry = 1000
        while retry > 0:
            try:
                ws = create_connection(
                    self.hype_ws_url,
                    sslopt={"cert_reqs": 0},
                )
                logger.info(f'Start Hyperliquid {self.symbol.upper()} OrderBook Monitor.')
                sub_msg = {
                    "method": "subscribe",
                    "subscription": {
                        "type": 'l2Book',
                        "coin": self.symbol.upper()
                    }
                }
                ws.send(json.dumps(sub_msg))
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    levels = message_dict['data'].get('levels')
                    if levels:
                        bids = [[float(bid['px']), float(bid['sz'])] for bid in levels[0][:level]]
                        asks = [[float(ask['px']), float(ask['sz'])] for ask in levels[1][:level]]
                        self.top_depth = {'bids': bids, 'asks': asks}
                        # print(self.top_depth)
                    await asyncio.sleep(0.0001)
                else:
                    logger.info(f'Complete the BN {self.symbol.upper()} Spot Top Depth monitor.')
                    return
            except Exception as e:
                logger.warning(f'Monitor BN {self.symbol.upper()} Spot Top Depth met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            logger.error(f'Failed to Monitor BN {self.symbol.upper()} Spot Top Depth after 1000 retries.')
    
    async def monitor_spot(self):
        # Use Binance Spot Aggr Trade Price as Spot mark price
        spot_url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}usdt@aggTrade"
        retry = 1000
        proxy_host = "127.0.0.1"
        proxy_port = 7897
        while retry > 0:
            try:
                ws = create_connection(
                    spot_url,
                    sslopt={"cert_reqs": 0},
                    http_proxy_host=proxy_host,
                    http_proxy_port=proxy_port,
                )
                logger.info(f'Start Binance Spot {self.symbol.upper()} Price Monitor.')
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    price = float(message_dict['p'])
                    self.spot_price = price
                    await asyncio.sleep(0.0001)
                else:
                    logger.info(f'Complete the BN {self.symbol.upper()} Spot price monitor.')
                    return
            except Exception as e:
                logger.warning(f'Monitor BN {self.symbol.upper()} Spot price met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            logger.error(f'Failed to Monitor BN {self.symbol.upper()} Spot price after 1000 retries.')

if __name__ == '__main__':
    connector = HypeFeedsConnector('eth')
    asyncio.run(connector.monitor_perp_top_depth())
    # asyncio.run(connector.monitor_spot())