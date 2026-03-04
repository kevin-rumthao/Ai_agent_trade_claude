"""Utility for splitting time-series data into train/validation/test sets."""
import pandas as pd
from typing import Tuple


def split_data_temporal(
    df: pd.DataFrame,
    train_pct: float = 0.7,
    val_pct: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data temporally (chronologically) into train/val/test.
    
    This is critical for time-series data to prevent data leakage.
    We split based on temporal order, not randomly.
    
    Args:
        df: Input dataframe (must be sorted by timestamp)
        train_pct: Percentage for training (default 0.7 = 70%)
        val_pct: Percentage for validation (default 0.2 = 20%)
        
    Returns:
        Tuple of (train_df, val_df, test_df)
        
    Example:
        >>> train, val, test = split_data_temporal(df)
        >>> len(train) / len(df)  # ~0.7
        >>> len(val) / len(df)    # ~0.2
        >>> len(test) / len(df)   # ~0.1
    """
    assert train_pct + val_pct < 1.0, "train_pct + val_pct must be < 1.0"
    
    n = len(df)
    train_end = int(n * train_pct)
    val_end = int(n * (train_pct + val_pct))
    
    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()
    
    print(f"Data Split:")
    print(f"  Train: {len(train_df):,} rows ({len(train_df)/n*100:.1f}%)")
    print(f"  Val:   {len(val_df):,} rows ({len(val_df)/n*100:.1f}%)")
    print(f"  Test:  {len(test_df):,} rows ({len(test_df)/n*100:.1f}%)")
    
    return train_df, val_df, test_df


def get_split_by_name(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    split_name: str
) -> pd.DataFrame:
    """
    Get a specific data split by name.
    
    Args:
        train_df, val_df, test_df: The three splits
        split_name: One of 'train', 'val', 'test'
        
    Returns:
        Requested dataframe split
    """
    splits = {
        'train': train_df,
        'val': val_df,
        'validation': val_df,
        'test': test_df
    }
    
    if split_name not in splits:
        raise ValueError(f"Invalid split name '{split_name}'. Must be one of: {list(splits.keys())}")
    
    return splits[split_name]
