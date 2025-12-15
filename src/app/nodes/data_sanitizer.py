from typing import TypedDict, List
from app.schemas.events import KlineEvent
import logging

logger = logging.getLogger(__name__)

def sanitize_data_node(state: dict) -> dict:
    """Filter out invalid klines from the state."""
    klines = state.get("klines", [])
    if not klines:
        return state

    valid_klines = []
    dropped_count = 0

    for k in klines:
        try:
            # Check for sanity
            # 1. Price > 0
            if k.close <= 0 or k.open <= 0 or k.high <= 0 or k.low <= 0:
                dropped_count += 1
                continue
            
            # 2. High >= Low
            if k.high < k.low:
                dropped_count += 1
                continue
            
            # 3. Volume >= 0
            if k.volume < 0:
                dropped_count += 1
                continue

            # Additional checks could go here (e.g. outlier detection)
            
            valid_klines.append(k)
        except Exception:
            dropped_count += 1

    if dropped_count > 0:
        logger.warning(f"[Sanitizer] Dropped {dropped_count} invalid klines")

    # Important: Return existing state updated with filtered klines
    return {**state, "klines": valid_klines}
