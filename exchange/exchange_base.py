

class Exchange():
    def __init__(self, exchange_name: str, api_key: str, secret_key: str):
        '''
            Initialize the ExchangeBase instance.

            Args:
                exchange_name (str): The name of the exchange (e.g., 'Binance', 'Coinbase').
                api_key (str): The API key for authenticating requests.
                secret_key (str): The secret key corresponding to the API key.

            Attributes:
                spot_client: Placeholder for spot trading client, initialized as None.
                perp_client: Placeholder for perpetual futures trading client, initialized as None.
        '''
        self.exchange_name = exchange_name
        self._key = api_key
        self._secret = secret_key
        self.spot_client = None
        self.perp_client = None

    async def put_spot_limit_order(self, symbol: str, side: str, quantity: float, price: float, gtx_only: bool = False) -> tuple[bool, str]:
        '''
            Asynchronously places a spot limit order.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The amount of the asset to buy or sell.
                price (float): The limit price for the order.
                gtx_only (bool): If True, the order will be Post Only (GTX), ensuring it does not match immediately with existing orders. Default is False.

            Returns:
                tuple[bool, str]: A tuple where the first element indicates success (True or False),
                              and the second element is the order ID if successful, or an error message if failed.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def put_spot_market_order(self, symbol: str, side: str, quantity: float) -> tuple[bool, float | str]:
        '''
            Asynchronously places a spot market order.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The amount of the asset to buy or sell.

            Returns:
                tuple[bool, float]: A tuple where:
                    - The first element is a boolean indicating whether the order was successfully executed.
                    - The second element is the final average price at which the market order was filled. 
                    If the order failed, this value may be 0.0 or undefined depending on implementation.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def cancel_spot_order(self, symbol: str, order_id: str) -> bool:
        '''
            Asynchronously cancels a spot order.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                order_id (str): The unique identifier of the order to cancel.

            Returns:
                bool: True if the cancellation was successful, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def adjust_spot_order(self, symbol: str, order_id: str) -> bool:
        '''
            Asynchronously adjusts an existing spot order.

            This method can be used to modify certain properties of an existing order 
            (such as price or quantity), depending on exchange support and implementation.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                order_id (str): The unique identifier of the order to adjust.

            Returns:
                bool: True if the order adjustment was successful, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def cancel_all_spot_orders(self, symbol: str) -> bool:
        '''
            Asynchronously cancels all open spot orders for a given trading pair.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.

            Returns:
                bool: True if all orders were successfully cancelled, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def put_perp_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> str:
        '''
            Asynchronously places a perpetual futures limit order.

            Args:
                symbol (str): The perpetual contract symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The quantity of contracts to buy or sell.
                price (float): The limit price for the order.

            Returns:
                str: The order ID returned after the order is successfully placed.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def put_perp_market_order(self, symbol: str, side: str, quantity: float) -> tuple[bool, float | str]:
        '''
            Asynchronously places a perpetual futures market order.

            Args:
                symbol (str): The perpetual contract symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The quantity of contracts to buy or sell.

            Returns:
                tuple[bool, float]: A tuple where:
                    - The first element is a boolean indicating whether the order was successfully executed.
                    - The second element is the final average execution price.
                    If the order fails, the price may be 0.0 or undefined depending on the implementation.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError
    
    async def put_perp_trigger_order(self, symbol: str, side: str, quantity: float, trigger_price: float) -> str:
        '''
            Asynchronously places a perpetual futures trigger order (stop order).

            Args:
                symbol (str): The perpetual contract symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The quantity of contracts to buy or sell.
                trigger_price (float): The price at which the trigger order will be activated.

            Returns:
                str: The order ID of the placed trigger order.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError


    async def put_perp_gtx_order(self, symbol: str, side: str, quantity: float, max_try=30) -> tuple[bool, float | str]:
        '''
            Asynchronously places a perpetual futures GTX (post-only) order with multiple retry attempts 
            until the target quantity is filled or maximum tries are exhausted.

            Args:
                symbol (str): The perpetual contract symbol, e.g., 'BTC/USDT'.
                side (str): Order side, either 'buy' or 'sell'.
                quantity (float): The total quantity of contracts to fill.
                max_try (int, optional): Maximum number of attempts to place GTX orders until 
                                        the target quantity is filled. Defaults to 30.

            Returns:
                tuple[bool, float]: A tuple where:
                    - The first element is a boolean indicating whether the target quantity was fully filled.
                    - The second element is the average price at which the quantity was filled.
                    If not successful, price may be 0.0 or undefined depending on implementation.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def cancel_perp_order(self, symbol: str, order_id: str) -> bool:
        '''
            Asynchronously cancels a perpetual futures order.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                order_id (str): The unique identifier of the order to cancel.

            Returns:
                bool: True if the cancellation was successful, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def adjust_perp_order(self, symbol: str, order_id: str) -> bool:
        '''
            Asynchronously adjusts an existing perpetual futures order.

            This method can be used to modify certain properties of an existing order 
            (such as price or quantity), depending on exchange support and implementation.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.
                order_id (str): The unique identifier of the order to adjust.

            Returns:
                bool: True if the order adjustment was successful, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError

    async def cancel_all_perp_orders(self, symbol: str) -> bool:
        '''
            Asynchronously cancels all open perpetual futures orders for a given trading pair.

            Args:
                symbol (str): The trading pair symbol, e.g., 'BTC/USDT'.

            Returns:
                bool: True if all orders were successfully cancelled, False otherwise.

            Raises:
                NotImplementedError: This method should be implemented by subclasses.
        '''
        raise NotImplementedError