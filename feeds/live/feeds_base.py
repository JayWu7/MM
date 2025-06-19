

class FeedsConnector():
    def __init__(self, token):
        self.token = token.strip().lower()
        self.is_closed = False
        self.spot_price = None
        self.usdt_perp_price = None
        self.usdc_perp_price = None
        self.top_depth = None