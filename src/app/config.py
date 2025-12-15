"""Configuration for the trading system.

Provides compatibility if `pydantic-settings` is not installed by falling back
to a lightweight environment-variable reader so tests and basic usage still run.
"""
from typing import Optional
import os
from pathlib import Path

# Load .env file explicitly
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # dotenv not available, use existing env vars

try:  # Prefer Pydantic v2 settings if available
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
    PydanticSettingsAvailable = True
except Exception:  # pragma: no cover - env-dependent
    BaseSettings = object  # type: ignore
    SettingsConfigDict = dict  # type: ignore
    PydanticSettingsAvailable = False


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    if PydanticSettingsAvailable:
        # Only used when pydantic-settings is available
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

    # API Keys
    binance_api_key: str = ""
    binance_api_secret: str = ""
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    # Gemini API key (used instead of Anthropic)
    gemini_api_key: str = ""

    # Kotak Neo API Keys
    kotak_consumer_key: str = ""
    kotak_mobile_number: str = ""
    kotak_password: str = ""  # MPIN or Password
    kotak_totp_secret: str = ""  # For generating TOTP if needed


    # Trading Provider Selection
    # Options: "binance" or "alpaca"
    trading_provider: str = "binance"

    # Trading Configuration
    symbol: str = "BTCUSDT"
    testnet: bool = True

    # Reliability
    MAX_RETRIES: int = 3
    RETRY_DELAY_MIN: float = 1.0
    RETRY_DELAY_MAX: float = 10.0

    # Risk Limits
    REQUIRE_STOP_LOSS: bool = True
    STOP_LOSS_PCT: float = 0.02  # Default 2% hard stop

    # Risk Parameters
    max_position_size: float = 0.1  # BTC
    max_drawdown_percent: float = 10.0
    max_daily_loss: float = 1000.0  # USD
    risk_per_trade_percent: float = 0.01
    risk_per_trade_percent: float = 0.01
    atr_stop_multiplier: float = 2.0
    target_volatility: float = 0.20  # Annualized (20%)

    # Strategy Parameters
    ema_short_period: int = 9
    ema_long_period: int = 50
    atr_period: int = 14
    volatility_lookback: int = 20
    
    # Mean Reversion Parameters
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    bollinger_period: int = 20
    bollinger_std_dev: float = 2.0

    # LLM Configuration (Gemini)
    llm_model: str = "gemini-pro-latest"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024

    # Application Settings
    log_level: str = "INFO"
    enable_backtesting: bool = False
    backtest_data_path: Optional[str] = None
    # Trading permissions/constraints
    allow_shorting: bool = False
    # Main loop
    loop_interval_seconds: int = 60
    # Optional: Limit iterations (0 = unlimited)
    max_iterations: int = 0
    # Optional: Time limit in hours (0 = unlimited)
    time_limit_hours: float = 0.0

    # Fallback __init__ when pydantic-settings is not available
    def __init__(self, **kwargs):  # type: ignore[override]
        if PydanticSettingsAvailable:
            super().__init__(**kwargs)  # type: ignore[misc]
        else:  # Manual env reading fallback
            # API Keys
            self.binance_api_key = os.getenv("BINANCE_API_KEY", "")
            self.binance_api_secret = os.getenv("BINANCE_API_SECRET", "")
            self.alpaca_api_key = os.getenv("ALPACA_API_KEY", "")
            self.alpaca_api_secret = os.getenv("ALPACA_API_SECRET", "")
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

            # Kotak Neo API Keys
            self.kotak_consumer_key = os.getenv("KOTAK_CONSUMER_KEY", "")
            self.kotak_mobile_number = os.getenv("KOTAK_MOBILE_NUMBER", "")
            self.kotak_password = os.getenv("KOTAK_PASSWORD", "")
            self.kotak_totp_secret = os.getenv("KOTAK_TOTP_SECRET", "")

            # Trading Provider Selection
            self.trading_provider = os.getenv("TRADING_PROVIDER", "binance")

            # Trading Configuration
            self.symbol = os.getenv("SYMBOL", "BTCUSDT")
            self.testnet = os.getenv("TESTNET", "true").lower() in {"1", "true", "yes"}

            # Reliability
            self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
            self.RETRY_DELAY_MIN = float(os.getenv("RETRY_DELAY_MIN", "1.0"))
            self.RETRY_DELAY_MAX = float(os.getenv("RETRY_DELAY_MAX", "10.0"))

            # Risk Limits
            self.REQUIRE_STOP_LOSS = os.getenv("REQUIRE_STOP_LOSS", "true").lower() in {"1", "true", "yes"}
            self.STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.02"))

            # Risk Parameters
            self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "0.1"))
            self.max_drawdown_percent = float(os.getenv("MAX_DRAWDOWN_PERCENT", "10.0"))
            self.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "1000.0"))
            self.risk_per_trade_percent = float(os.getenv("RISK_PER_TRADE_PERCENT", "0.01"))
            self.atr_stop_multiplier = float(os.getenv("ATR_STOP_MULTIPLIER", "2.0"))

            # Strategy Parameters
            self.ema_short_period = int(os.getenv("EMA_SHORT_PERIOD", "9"))
            self.ema_long_period = int(os.getenv("EMA_LONG_PERIOD", "50"))
            self.atr_period = int(os.getenv("ATR_PERIOD", "14"))
            self.volatility_lookback = int(os.getenv("VOLATILITY_LOOKBACK", "20"))
            
            # Mean Reversion Parameters
            self.rsi_period = int(os.getenv("RSI_PERIOD", "14"))
            self.rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", "70"))
            self.rsi_oversold = int(os.getenv("RSI_OVERSOLD", "30"))
            self.bollinger_period = int(os.getenv("BOLLINGER_PERIOD", "20"))
            self.bollinger_std_dev = float(os.getenv("BOLLINGER_STD_DEV", "2.0"))

            # LLM Configuration (Gemini)
            self.llm_model = os.getenv("LLM_MODEL", "gemini-pro-latest")
            self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
            self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1024"))

            # Application Settings
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.enable_backtesting = os.getenv("ENABLE_BACKTESTING", "false").lower() in {"1", "true", "yes"}
            self.backtest_data_path = os.getenv("BACKTEST_DATA_PATH")
            self.allow_shorting = os.getenv("ALLOW_SHORTING", "false").lower() in {"1", "true", "yes"}
            self.loop_interval_seconds = int(os.getenv("LOOP_INTERVAL_SECONDS", "60"))
            self.max_iterations = int(os.getenv("MAX_ITERATIONS", "0"))
            self.time_limit_hours = float(os.getenv("TIME_LIMIT_HOURS", "0.0"))


# Global settings instance
settings = Settings()
