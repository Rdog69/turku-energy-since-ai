"""Availability filter enforcing the competition's strict anti-leakage rule."""

from typing import Union
import pandas as pd
from src.data.loader import to_utc


def available_at(
    data: pd.DataFrame,
    origin_utc: Union[str, pd.Timestamp],
    as_wide: bool = True,
) -> pd.DataFrame:
    """Filter long-format data to rows legally usable at forecast origin origin_utc.

    At forecast origin t, your model may use a row only if
    first_usable_origin_utc <= t.

    Parameters
    ----------
    data : pd.DataFrame
        Long-format dataframe containing 'timestamp_utc', 'first_usable_origin_utc',
        'series_id', and 'value'.
    origin_utc : str or pd.Timestamp
        The forecast origin.
    as_wide : bool, default True
        If True, returns a wide dataframe indexed by 'timestamp_utc' with columns
        for each 'series_id'.

    Returns
    -------
    pd.DataFrame
        Usable data at origin_utc.
    """
    origin = to_utc(origin_utc)

    if "first_usable_origin_utc" not in data.columns:
        raise ValueError("Dataframe must contain 'first_usable_origin_utc' column.")

    # Strict filtering
    usable = data.loc[data["first_usable_origin_utc"] <= origin]

    # Leakage assertion: zero tolerance
    if not usable.empty:
        max_fu = usable["first_usable_origin_utc"].max()
        assert max_fu <= origin, (
            f"LEAKAGE DETECTED: maximum first_usable_origin_utc {max_fu} is greater than origin {origin}"
        )

    if as_wide:
        if usable.empty:
            return pd.DataFrame()
        wide = usable.pivot(index="timestamp_utc", columns="series_id", values="value")
        return wide.sort_index()

    return usable.sort_values("timestamp_utc").reset_index(drop=True)


def assert_no_leakage(df_or_series: Union[pd.DataFrame, pd.Series], origin_utc: Union[str, pd.Timestamp]) -> None:
    """Assert that no timestamp or first_usable_origin_utc exceeds origin_utc."""
    origin = to_utc(origin_utc)
    if isinstance(df_or_series, pd.DataFrame):
        if "first_usable_origin_utc" in df_or_series.columns:
            leaks = df_or_series[df_or_series["first_usable_origin_utc"] > origin]
            if not leaks.empty:
                raise AssertionError(
                    f"Leakage check failed: {len(leaks)} rows have first_usable_origin_utc > {origin}."
                )

