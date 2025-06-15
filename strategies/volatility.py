import numpy as np

class VolatilityEstimator:
    def __init__(self, short_window: int = 60, long_window: int = 600, ewma_lambda: float = 0.94):
        """
        Volatility estimator using a combination of short-term, long-term, and EWMA models.
        
        Parameters
        ----------
        short_window : int
            Window size (in number of price points) for short-term volatility calculation.
        long_window : int
            Window size for long-term volatility.
        ewma_lambda : float
            Smoothing factor for EWMA; closer to 1 means more weight on past volatility.
        """
        self.short_window = short_window
        self.long_window = long_window
        self.ewma_lambda = ewma_lambda
        self.ewma_vol_squared = 0.0

    def update(self, price_series: list[float]) -> dict:
        """
        Update and compute the current volatility using the input price series.
        
        Parameters
        ----------
        price_series : list of float
            Chronologically ordered price data (latest at the end).
        
        Returns
        -------
        dict
            A dictionary with short-term, long-term, EWMA, and effective volatilities.
        """
        if len(price_series) < 2:
            return {"short_vol": 0.0, "long_vol": 0.0, "ewma_vol": 0.0, "effective_vol": 0.0}
        
        log_returns = np.diff(np.log(price_series))

        short_returns = log_returns[-self.short_window:] if len(log_returns) >= self.short_window else log_returns
        long_returns = log_returns[-self.long_window:] if len(log_returns) >= self.long_window else log_returns

        short_vol = np.std(short_returns) * np.sqrt(60)
        long_vol = np.std(long_returns) * np.sqrt(60)

        if len(log_returns) > 0:
            latest_return = log_returns[-1]
            self.ewma_vol_squared = (
                self.ewma_lambda * self.ewma_vol_squared +
                (1 - self.ewma_lambda) * (latest_return ** 2)
            )

        ewma_vol = np.sqrt(self.ewma_vol_squared) * np.sqrt(60)

        effective_vol = 0.3 * short_vol + 0.4 * ewma_vol + 0.3 * long_vol

        return {
            "short_vol": short_vol,
            "long_vol": long_vol,
            "ewma_vol": ewma_vol,
            "effective_vol": effective_vol
        }
