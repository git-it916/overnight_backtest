import argparse
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

DATE_COL_CANDIDATES = ("date", "Date", "날짜", "일자", "거래일")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Overnight gap analysis for OHLC time series data."
    )
    parser.add_argument("path", help="Input Excel/CSV file path.")
    parser.add_argument("--sheet", help="Excel sheet name or index.")
    parser.add_argument("--encoding", help="CSV encoding (e.g. cp949).")
    parser.add_argument("--date-col", dest="date_col", help="Date column name.")
    parser.add_argument("--open-col", dest="open_col", help="Open column name.")
    parser.add_argument("--high-col", dest="high_col", help="High column name.")
    parser.add_argument("--low-col", dest="low_col", help="Low column name.")
    parser.add_argument("--close-col", dest="close_col", help="Close column name.")
    parser.add_argument("--volume-col", dest="volume_col", help="Volume column name.")
    return parser.parse_args()


def load_data(path, sheet=None, encoding=None):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path, sheet_name=sheet)
    return pd.read_csv(path, encoding=encoding)


def resolve_date_col(df, date_col):
    if date_col:
        if date_col not in df.columns:
            raise SystemExit(
                f"Date column '{date_col}' not found. "
                f"Available columns: {', '.join(df.columns)}"
            )
        return date_col
    for candidate in DATE_COL_CANDIDATES:
        if candidate in df.columns:
            return candidate
    return None

# =========================
# 1. 컬럼 정리 (필요 시 수정)
# =========================
rename_map = {
    "시가지수(포인트)": "open",
    "고가지수(포인트)": "high",
    "저가지수(포인트)": "low",
    "종가지수(포인트)": "close",
    "거래대금(원)": "turnover",
    "거래량 (5일 평균)(주)": "vol_ma5",
    "거래량 (20일 평균)(주)": "vol_ma20",
    "순매수대금(외국인계)(백만원)": "foreign_net",
    "순매수대금(기관/외국인인계)(백만원)": "inst_foreign_net"
}

dataguide_map = {
    "I31000010F": "open",
    "I31000020F": "high",
    "I31000030F": "low",
    "I31000040F": "close",
    "I31000050F": "volume"
}

args = parse_args()
df = load_data(args.path, args.sheet, args.encoding)

date_col = resolve_date_col(df, args.date_col)
if date_col:
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)

rename_map = {**rename_map, **dataguide_map}
for col_name, target in (
    (args.open_col, "open"),
    (args.high_col, "high"),
    (args.low_col, "low"),
    (args.close_col, "close"),
    (args.volume_col, "volume"),
):
    if col_name:
        rename_map[col_name] = target

df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
df = df.sort_index()

required_cols = ("open", "high", "low", "close")
missing = [col for col in required_cols if col not in df.columns]
if missing:
    raise SystemExit(
        f"Missing required columns after renaming: {', '.join(missing)}. "
        "Use --open-col/--high-col/--low-col/--close-col if needed."
    )

# =========================
# 2. Feature Engineering
# =========================
df["ret_1d"] = df["close"].pct_change()

# 오버나이트 갭
df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)

# 오프닝 확장 proxy
df["open_to_high"] = (df["high"] - df["open"]) / df["open"]
df["open_to_low"]  = (df["low"] - df["open"]) / df["open"]

df["range"] = df["high"] - df["low"]
df["dir_ratio_long"]  = (df["high"] - df["open"]) / df["range"]
df["dir_ratio_short"] = (df["open"] - df["low"]) / df["range"]

# True Range / ATR
tr = pd.concat([
    df["high"] - df["low"],
    (df["high"] - df["close"].shift(1)).abs(),
    (df["low"] - df["close"].shift(1)).abs()
], axis=1).max(axis=1)

df["atr20"] = tr.rolling(20).mean()
df["vol_regime"] = (df["atr20"] / df["close"]).rolling(20).rank(pct=True)

# =========================
# 3. 시각화
# =========================

# (1) 가격과 변동성 레짐
plt.figure()
df["close"].plot(title="MKF2000 Close Price")
plt.show()

plt.figure()
df["vol_regime"].plot(title="Volatility Regime (ATR-based Percentile)")
plt.axhline(0.8, linestyle="--")
plt.show()

# (2) 오버나이트 갭 분포
plt.figure()
df["gap"].hist(bins=60)
plt.title("Overnight Gap Distribution")
plt.show()

# (3) 오프닝 확장 분포
plt.figure()
df["open_to_high"].hist(bins=60)
plt.title("Open → High Expansion Distribution")
plt.show()

plt.figure()
df["open_to_low"].hist(bins=60)
plt.title("Open → Low Expansion Distribution")
plt.show()

# (4) 방향성 vs 노이즈
plt.figure()
df["dir_ratio_long"].hist(bins=60)
plt.title("Directional Ratio (Long)")
plt.show()

# (5) 수급 누적
if "foreign_net" in df.columns:
    plt.figure()
    df["foreign_net"].cumsum().plot(title="Cumulative Foreign Net Flow")
    plt.show()

if "inst_foreign_net" in df.columns:
    plt.figure()
    df["inst_foreign_net"].cumsum().plot(title="Cumulative Inst+Foreign Net Flow")
    plt.show()

# =========================
# 4. 조건부 분석 (전략에 핵심)
# =========================

# 오프닝 알파 '기회'가 있었던 날 정의
alpha_days = df[
    (df["open_to_high"] > 0.003) &
    (df["open_to_low"] > -0.0015) &
    (df["dir_ratio_long"] > 0.6)
]

print("Alpha opportunity days:", len(alpha_days))
print("Alpha days ratio:", len(alpha_days) / len(df))

# 수급 조건이 있을 때 확률 변화
if "foreign_net" in df.columns:
    cond = df["foreign_net"] > 0
    print("Alpha prob | Foreign Net > 0:",
          ((cond) & (df.index.isin(alpha_days.index))).sum() / cond.sum())

# =========================
# 5. 요약 통계
# =========================
summary = df[
    ["gap", "open_to_high", "open_to_low",
     "dir_ratio_long", "vol_regime"]
].describe()

print(summary)
