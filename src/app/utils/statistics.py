"""Statistical utilities for trading (ADF, Hurst, GARCH)."""
import numpy as np
import logging
from typing import Optional, Tuple, Literal

logger = logging.getLogger(__name__)

# Optional imports for heavy libraries to allow basic app partial function without them
try:
    from statsmodels.tsa.stattools import adfuller
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not found. Advanced statistics disabled.")

try:
    from arch import arch_model
    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False
    logger.warning("arch package not found. GARCH volatility disabled.")


def check_stationarity(timeseries: list[float], max_p_value: float = 0.05) -> Tuple[bool, float]:
    """
    Perform Augmented Dickey-Fuller test to check for stationarity.
    Returns (is_stationary, p_value).
    """
    if not STATSMODELS_AVAILABLE or len(timeseries) < 30:
        return False, 1.0

    try:
        # adfuller returns: adf, pvalue, usedlag, nobs, critical values, icbest
        result = adfuller(timeseries)
        p_value = result[1]
        is_stationary = p_value < max_p_value
        return is_stationary, float(p_value)
    except Exception as e:
        logger.error(f"ADF Test Error: {e}")
        return False, 1.0


def calculate_hurst(timeseries: list[float]) -> float:
    """
    Calculate Hurst Exponent to determine regime.
    H < 0.5: Mean Reverting
    H = 0.5: Random Walk
    H > 0.5: Trending
    """
    if len(timeseries) < 100:
        return 0.5

    try:
        lags = range(2, 20)
        tau = [np.sqrt(np.std(np.subtract(timeseries[lag:], timeseries[:-lag]))) for lag in lags]
        
        # Polyfit log(lags) vs log(tau) gives Hurst
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return float(poly[0]) * 2.0 
        # Note: various implementations exist. This is a simplified R/S proxy.
        # A more robust one might be needed if critical.
    except Exception as e:
        logger.error(f"Hurst calculation error: {e}")
        return 0.5


def forecast_volatility(returns: list[float], method: Literal['GARCH', 'EWMA'] = 'GARCH') -> Optional[float]:
    """
    Forecast next period volatility.
    Input 'returns' should be percentage returns (e.g., 0.01 for 1%).
    """
    if not returns or len(returns) < 30:
        return None

    # Handle GARCH
    if method == 'GARCH' and ARCH_AVAILABLE:
        try:
            # Rescale returns to be more friendly for optimizers (often expects integers like 1.0 for 1%)
            # But arch_model usually handles it. If returns are very small (0.0001), optimization fails.
            # Let's upscale by 100 for calculation then downscale.
            scaled_returns = [r * 100.0 for r in returns]
            
            am = arch_model(scaled_returns, vol='Garch', p=1, q=1, rescale=False)
            res = am.fit(disp='off', show_warning=False)
            
            # Forecast next volatility
            forecast = res.forecast(horizon=1)
            next_vol_scaled = np.sqrt(forecast.variance.values[-1, :])[0]
            
            return next_vol_scaled / 100.0
        except Exception as e:
            logger.warning(f"GARCH fitting failed: {e}. Falling back to std dev.")
    
    # Fallback to simple standard deviation (or EWMA logic)
    return float(np.std(returns))
