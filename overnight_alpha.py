from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
import pandas as pd


ITEM_CODE_MAP = {
    "I31000010F": "open",
    "I31000020F": "high",
    "I31000030F": "low",
    "I31000040F": "close",
    "I31000050F": "volume",
    "I310000600": "turnover",
    "I310021132": "foreign_net",
    "I310021232": "inst_net",
}

REQUIRED_COLS = ("open", "high", "low", "close")
ITEM_CODE_PATTERN = re.compile(r"^I\d{7,}[A-Za-z0-9]*$")


@dataclass(frozen=True)
class Params:
    gap_abs_max: float
    take_profit_opening: float
    stop_opening: float
    dir_ratio_thresh: float
    cost: float
    optimistic_fill: bool
    path_dependency_mode: str | None = None
    require_flow_data: bool = False


def _normalize_code(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value)
    text = text.replace("\u00A0", "")
    text = text.strip()
    if not text:
        return None
    if text.endswith(".0") and text.replace(".", "").isdigit():
        text = text[:-2]
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text or None


def _find_label_row(
    df_raw: pd.DataFrame, label: str, start_row: int = 0
) -> int | None:
    label = _normalize_code(label)
    if not label:
        return None
    for idx in range(start_row, len(df_raw)):
        row = df_raw.iloc[idx]
        for cell in row:
            cell_label = _normalize_code(cell)
            if cell_label and cell_label.lower() == label.lower():
                return idx
    return None


def _is_item_code(value) -> bool:
    normalized = _normalize_code(value)
    return bool(normalized and ITEM_CODE_PATTERN.match(normalized))


def _find_item_row(df_raw: pd.DataFrame) -> int | None:
    candidates = []
    for idx in range(len(df_raw)):
        row = df_raw.iloc[idx]
        if any(_normalize_code(cell) == "Item" for cell in row):
            code_count = sum(1 for cell in row if _is_item_code(cell))
            candidates.append((code_count, idx))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return candidates[0][1]


def _map_item_codes(df: pd.DataFrame) -> pd.DataFrame:
    normalized_map = {_normalize_code(code): name for code, name in ITEM_CODE_MAP.items()}
    rename_map = {}
    for col in df.columns:
        normalized = _normalize_code(col)
        if normalized and normalized in normalized_map:
            rename_map[col] = normalized_map[normalized]
    if not rename_map:
        return df
    mapped = df.rename(columns=rename_map)
    for col in rename_map.values():
        mapped[col] = pd.to_numeric(mapped[col], errors="coerce")
    return mapped


def load_dataguide_excel(path: str | Path, sheet_name: int | str = 0) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    item_row = _find_item_row(raw)
    if item_row is None:
        raise SystemExit("Could not locate the 'Item' row in the DataGuide file.")

    freq_row = _find_label_row(raw, "Frequency", start_row=item_row + 1)
    data_start = freq_row + 1 if freq_row is not None else item_row + 1

    item_values = raw.iloc[item_row].tolist()
    columns = [_normalize_code(value) for value in item_values]
    if not columns:
        raise SystemExit("No columns found in the DataGuide Item row.")

    columns[0] = "date"
    for idx in range(1, len(columns)):
        if not columns[idx]:
            columns[idx] = f"col_{idx}"

    data = raw.iloc[data_start:].copy()
    data.columns = columns
    data = data.dropna(how="all")

    if "date" not in data.columns:
        raise SystemExit("Date column not found after parsing the Item row.")

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data = data.set_index("date").sort_index()

    data = _map_item_codes(data)
    return data


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing:
        missing_text = ", ".join(missing)
        available = sorted(
            {
                _normalize_code(col)
                for col in df.columns
                if _normalize_code(col)
            }
        )
        preview = ", ".join(available[:20])
        suffix = "..." if len(available) > 20 else ""
        raise SystemExit(
            "Missing required Item codes for OHLC mapping. "
            f"Required columns after mapping: {missing_text}. "
            f"Available item codes (normalized): {preview}{suffix}"
        )


def _resolve_path_dependency_mode(params: Params) -> str:
    if params.path_dependency_mode:
        mode = params.path_dependency_mode
    else:
        mode = "optimistic" if params.optimistic_fill else "conservative"
    mode = mode.lower()
    if mode not in {"optimistic", "conservative", "trend"}:
        raise SystemExit(f"Unsupported path_dependency_mode: {mode}")
    return mode


def run_opening_proxy_backtest(
    df: pd.DataFrame, direction: pd.Series, params: Params
) -> pd.DataFrame:
    d = df.join(direction.rename("direction"), how="inner").copy()
    d = d.dropna(subset=["direction", "open", "high", "low", "close"])

    prev_close = d["close"].shift(1)
    d["pnl_overnight"] = d["direction"] * ((d["open"] / prev_close) - 1.0)

    open_to_high = (d["high"] - d["open"]) / d["open"]
    open_to_low = (d["low"] - d["open"]) / d["open"]
    open_to_close = (d["close"] - d["open"]) / d["open"]

    long_tp_hit = open_to_high >= params.take_profit_opening
    long_sl_hit = open_to_low <= -params.stop_opening
    short_tp_hit = open_to_low <= -params.take_profit_opening
    short_sl_hit = open_to_high >= params.stop_opening

    long_close = open_to_close
    short_close = -open_to_close

    mode = _resolve_path_dependency_mode(params)
    if mode == "trend":
        pnl_opening = np.where(
            d["direction"] == 1,
            long_close,
            np.where(d["direction"] == -1, short_close, 0.0),
        )
    elif mode == "optimistic":
        long_choice = np.select(
            [long_tp_hit, long_sl_hit],
            [params.take_profit_opening, -params.stop_opening],
            default=long_close,
        )
        short_choice = np.select(
            [short_tp_hit, short_sl_hit],
            [params.take_profit_opening, -params.stop_opening],
            default=short_close,
        )
        pnl_opening = np.where(
            d["direction"] == 1,
            long_choice,
            np.where(d["direction"] == -1, short_choice, 0.0),
        )
    else:
        long_choice = np.select(
            [long_sl_hit, long_tp_hit],
            [-params.stop_opening, params.take_profit_opening],
            default=long_close,
        )
        short_choice = np.select(
            [short_sl_hit, short_tp_hit],
            [-params.stop_opening, params.take_profit_opening],
            default=short_close,
        )
        pnl_opening = np.where(
            d["direction"] == 1,
            long_choice,
            np.where(d["direction"] == -1, short_choice, 0.0),
        )

    d["pnl_opening"] = pnl_opening
    pnl_gross = d["pnl_overnight"] + d["pnl_opening"]
    trade_allowed = d["direction"] != 0
    d["pnl_net"] = np.where(trade_allowed, pnl_gross - params.cost, 0.0)
    d["equity"] = (1.0 + d["pnl_net"].fillna(0)).cumprod()
    return d[["direction", "pnl_overnight", "pnl_opening", "pnl_net", "equity"]]


def run_alpha_factor_testing(
    df: pd.DataFrame, params: Params
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    df = df.copy()
    df = _map_item_codes(df)
    _validate_required_columns(df)

    df_features = pd.DataFrame(index=df.index)
    prev_close = df["close"].shift(1)
    df_features["gap"] = (df["open"] - prev_close) / prev_close
    df_features["ret_1d"] = df["close"].pct_change()
    df_features["open_to_high"] = (df["high"] - df["open"]) / df["open"]
    df_features["open_to_low"] = (df["low"] - df["open"]) / df["open"]

    price_range = (df["high"] - df["low"]).replace(0, np.nan)
    df_features["dir_ratio_long"] = (df["high"] - df["open"]) / price_range
    df_features["dir_ratio_short"] = (df["open"] - df["low"]) / price_range

    cond = (
        (df_features["open_to_high"] >= params.take_profit_opening)
        & (df_features["open_to_low"] >= -params.stop_opening)
        & (df_features["dir_ratio_long"] >= params.dir_ratio_thresh)
        & (df_features["gap"].abs() <= params.gap_abs_max)
    )
    signal = cond.shift(1).fillna(False)
    direction = signal.astype(int)
    if params.require_flow_data:
        flow_cols = {"foreign_net", "inst_net"}
        if not flow_cols.issubset(df.columns):
            direction = pd.Series(0, index=df.index, dtype=int)

    backtest = run_opening_proxy_backtest(df, direction, params)

    heatmaps = {
        "feature_corr": df_features[
            ["gap", "open_to_high", "open_to_low", "dir_ratio_long"]
        ].corr()
    }

    df_features["direction"] = direction
    return df_features, heatmaps, backtest
