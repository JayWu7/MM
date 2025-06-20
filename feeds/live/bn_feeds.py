import json
import asyncio
import logging
from websocket import create_connection
from feeds_base import FeedsConnector

logger = logging.getLogger(__name__)

class BnFeedsConnector(FeedsConnector):
    def __init__(self, symbol):
        super().__init__(symbol)

    async def monitor_spot(self):
        spot_url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@aggTrade"
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


    async def monitor_perp(self):
        base_url = "wss://fstream.binance.com/ws"
        stream = f"{self.symbol.lower()}@aggTrade"
        url = f"{base_url}/{stream}"

        retry = 1000
        while retry > 0:
            try:
                ws = create_connection(
                    url,
                    sslopt={"cert_reqs": 0},  
                )
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    price = float(message_dict['p'])
                    self.usdt_perp_price = price
                    await asyncio.sleep(0.0001)
                else:
                    logger.info(f'Complete the BN {self.symbol.upper()} perp price monitor.')
                    return
            except Exception as e:
                logger.warning(f'Monitor BN {self.symbol.upper()} perp price met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            logger.error(f'Failed to Monitor BN {self.symbol.upper()} perp price after 1000 retries.')
    

    async def monitor_top_depth(self, level=10):
        assert level in [5, 10, 20], 'The top level must be 5, 10 or 20.'
        top_depth_url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@depth{level}@100ms"
        retry = 1000
        proxy_host = "127.0.0.1"
        proxy_port = 7897
        while retry > 0:
            try:
                ws = create_connection(
                    top_depth_url,
                    http_proxy_host=proxy_host,
                    http_proxy_port=proxy_port,
                    sslopt={"cert_reqs": 0},
                )
                logger.info(f'Start Binance Spot {self.symbol.upper()} OrderBook Monitor.')
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    self.top_depth = {'bids': message_dict['bids'], 'asks': message_dict['asks']}
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
    

if __name__ == '__main__':
    connector = BnFeedsConnector('btc')
    asyncio.run(connector.monitor_spot_top_depth())