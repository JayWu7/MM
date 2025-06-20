from binance.spot import Spot

def bn_klines(symbol: str, interval: int = 1, limit: int = 1000) -> list | None:

    retry = 5
    while retry > 0:
        try:
            client = Spot()
            k_data = client.klines(symbol=symbol, interval=f'{interval}s', limit=limit) 
            assert type(k_data) == list and len(k_data) == limit, 'Fetch binance kline data met error.'
            return k_data
        except Exception as e:
            print(e)
            retry -= 1
    else:
        return None

def bn_klines_close_price(symbol: str, interval: int = 1, limit: int = 1000) -> list | None:

    retry = 5
    while retry > 0:
        try:
            client = Spot()
            k_data = client.klines(symbol=symbol, interval=f'{interval}s', limit=limit) 
            assert type(k_data) == list and len(k_data) == limit, 'Fetch binance kline data met error.'
            c_prices = [float(k[4]) for k in k_data]
            return c_prices
        except Exception as e:
            print(e)
            retry -= 1
    else:
        return None
    

if __name__ == '__main__':
    print(bn_klines_close_price('BTCUSDT')[:2])