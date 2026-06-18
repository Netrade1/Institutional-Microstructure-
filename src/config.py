"""
config.py – Centralised system configuration loaded from environment variables.
All subsystems import from here; never read os.environ directly in business logic.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project layout ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
AUDIT_LOG_DIR = ROOT_DIR / os.getenv("AUDIT_LOG_DIR", "data/audit_logs")
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Data feeds ────────────────────────────────────────────────────────────────
POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")
ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
DEFAULT_FEED: str = os.getenv("DEFAULT_FEED", "sample")
DEFAULT_SYMBOL: str = os.getenv("DEFAULT_SYMBOL", "AAPL")

# ── LLM ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── DeepSeek (Phase 2A – Motivation Inference Engine) ─────────────────────────
# DeepSeek-R1 is accessed via an OpenAI-compatible API.
# Self-hosted local deployment is the preferred option for data sovereignty.
# Leave DEEPSEEK_API_KEY blank to use the rule-based motivation engine only.
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")

# ── Storage ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/microstructure.db")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Execution mode ────────────────────────────────────────────────────────────
EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "paper").lower()
LIVE_MODE_ENABLED: bool = EXECUTION_MODE == "live"

# ── Risk defaults ─────────────────────────────────────────────────────────────
MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "2.0"))
MAX_POSITION_SIZE_PCT: float = float(os.getenv("MAX_POSITION_SIZE_PCT", "5.0"))
MAX_SPREAD_MULTIPLE: float = float(os.getenv("MAX_SPREAD_MULTIPLE", "3.0"))
MIN_MODEL_CONFIDENCE: float = float(os.getenv("MIN_MODEL_CONFIDENCE", "0.55"))
MIN_DATA_QUALITY_SCORE: float = float(os.getenv("MIN_DATA_QUALITY_SCORE", "0.80"))

# ── Order book processing ─────────────────────────────────────────────────────
OB_DEPTH_LEVELS: int = 10          # number of price levels to track each side
OB_WINDOW_SECONDS: int = 90        # rolling window for imbalance metrics
SWEEP_PRICE_LEVELS: int = 3        # consecutive levels crossed = sweep event
ABSORPTION_MIN_PRINTS: int = 5     # minimum prints to qualify as absorption event
SPOOF_MIN_CANCEL_RATIO: float = 4.0  # cancel-to-add ratio threshold for spoof flag

# ── Feature engineering ───────────────────────────────────────────────────────
FEATURE_WINDOWS: list[int] = [5, 10, 30, 60, 300]   # seconds
RSI_PERIOD: int = 14
ATR_PERIOD: int = 14
VWAP_SESSION_RESET: bool = True

# ── Compliance hardcoded constants ────────────────────────────────────────────
IDENTITY_CLAIM_BLOCKED_TERMS: list[str] = [
    "blackrock", "citadel", "vanguard", "jane street", "two sigma",
    "renaissance", "bridgewater", "millennium", "point72", "d.e. shaw",
    "virtu", "jump trading", "susquehanna", "optiver", "imc",
]
COMPLIANCE_LIMITATIONS_STATEMENT: str = (
    "Level 2 data does not reveal the actual identity of market participants. "
    "All behavioral classifications are probabilistic estimates based on "
    "observable, legally accessible market data only."
)

# ── IPO configuration (Phase 2A) ─────────────────────────────────────────────
# Symbols in this list receive additional IPO microstructure analysis.
# Update with the active IPO ticker(s) you are monitoring.
IPO_SYMBOLS: list[str] = [s.strip().upper() for s in os.getenv("IPO_SYMBOLS", "SPCX").split(",") if s.strip()]
