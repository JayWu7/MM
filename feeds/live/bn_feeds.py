import json
import asyncio
from websocket import create_connection
from colorama import init, Fore
init(autoreset=True)


class BnFeedsConnector():
    def __init__(self, token):
        self.token = token.strip().lower()
        self.is_closed = False
        self.spot_price = None
        self.usdt_perp_price = None
        self.usdc_perp_price = None
        self.top_depth = None

    async def monitor_spot(self):
        spot_url = f"wss://stream.binance.com:9443/ws/{self.token}usdt@aggTrade"
        retry = 1000
        while retry > 0:
            try:
                ws = create_connection(
                    spot_url,
                    sslopt={"cert_reqs": 0},
                )
                i = 0
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    price = float(message_dict['p'])
                    self.spot_price = price
                    if i % 1000 == 0:
                        print(Fore.CYAN + f"Current Binance {self.token} Spot price: {price}")
                    i += 1
                    await asyncio.sleep(0.0001)
                else:
                    print(Fore.BLACK + f'Complete the BN {self.token} Spot price monitor.')
                    return
            except Exception as e:
                print(Fore.BLACK + f'Monitor BN {self.token} Spot price met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            print(Fore.BLACK + f'Failed to Monitor BN {self.token} Spot price after 1000 retries.')
    

    async def monitor_usdc_perp(self):
        base_url = "wss://fstream.binance.com/ws"
        stream = f"{self.token}usdc@aggTrade"
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
                    self.usdc_perp_price = price
                    await asyncio.sleep(0.0001)
                    print(message)
                else:
                    print(Fore.BLACK + f'Complete the BN {self.token.upper()}-USDC perp price monitor.')
                    return
            except Exception as e:
                print(Fore.RED + f'Monitor BN {self.token.upper()}-USDC perp price met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            print(Fore.RED + f'Failed to Monitor BN {self.token.upper()}-USDC perp price after 1000 retries.')


    async def monitor_usdt_perp(self):
        base_url = "wss://fstream.binance.com/ws"
        stream = f"{self.token}usdt@aggTrade"
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
                    print(message)
                else:
                    print(Fore.BLACK + f'Complete the BN {self.token.upper()}-USDT perp price monitor.')
                    return
            except Exception as e:
                print(Fore.RED + f'Monitor BN {self.token.upper()}-USDT perp price met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            print(Fore.RED + f'Failed to Monitor BN {self.token.upper()}-USDT perp price after 1000 retries.')
    

    async def monitor_spot_top_depth(self, level=10):
        assert level in [5, 10, 20], 'The top level must be 5, 10 or 20.'
        top_depth_url = f"wss://stream.binance.com:9443/ws/{self.token}usdt@depth{level}@100ms"
        retry = 1000
        while retry > 0:
            try:
                ws = create_connection(
                    top_depth_url,
                    sslopt={"cert_reqs": 0},
                )
                while not self.is_closed:
                    message = ws.recv()
                    message_dict = json.loads(message)
                    self.top_depth = {'bids': message_dict['bids'], 'asks': message_dict['asks']}
                    print(self.top_depth)
                    await asyncio.sleep(0.0001)
                else:
                    print(Fore.BLACK + f'Complete the BN {self.token} Spot Top Depth monitor.')
                    return
            except Exception as e:
                print(Fore.BLACK + f'Monitor BN {self.token} Spot Top Depth met error: {e}, retry.')
                retry -= 1
                await asyncio.sleep(0.5)
        else:
            print(Fore.BLACK + f'Failed to Monitor BN {self.token} Spot Top Depth after 1000 retries.')
    

if __name__ == '__main__':
    connector = BnFeedsConnector('btc')
    asyncio.run(connector.monitor_spot_top_depth())