"""Persistence utility for saving and loading application state."""
import json
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class StateManager:
    """Manages state persistence to disk."""

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        """Get file path for a given key, sanitizing special characters."""
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.data_dir / f"{safe_key}.json"

    def save_state(self, key: str, data: Dict[str, Any]) -> bool:
        """
        Save state to disk as JSON.
        
        Uses atomic write pattern (write to temp, then rename) to prevent corruption.
        """
        file_path = self._get_path(key)
        temp_path = file_path.with_suffix(".tmp")
        
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Atomic rename
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state for {key}: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    def load_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Load state from disk."""
        file_path = self._get_path(key)
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load state for {key}: {e}")
            return None
            
    def clear_state(self, key: str) -> bool:
        """Delete state file."""
        file_path = self._get_path(key)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete state for {key}: {e}")
                return False
        return True

# Global instance
persistence = StateManager()
