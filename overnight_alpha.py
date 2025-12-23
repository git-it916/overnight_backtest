from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import pandas as pd

# ==============================================================================
# 1. 데이터 매핑 (사모펀드 포함)
# ==============================================================================
ITEM_CODE_MAP = {
    "I31000010F": "open",
    "I31000020F": "high",
    "I31000030F": "low",
    "I31000040F": "close",
    "I310000600": "turnover",      # 거래대금
    "I310020932": "net_priv_fund", # 사모펀드 순매수 (핵심)
    "I310023132": "net_foreign",   # 외국인계 (참고)
}

# ==============================================================================
# 2. 파라미터 클래스 (핵심 변수 4개만 남김 - 오류 원인 제거)
# ==============================================================================
@dataclass(frozen=True)
class Params:
    rolling_window: int = 60       # 랭크 산정 기간 (60일)
    buy_threshold: float = 0.10    # 매수 기준 (하위 10%)
    sell_threshold: float = 0.90   # 매도 기준 (상위 10%)
    cost: float = 0.0015           # 거래비용 (0.15%)

# ==============================================================================
# 3. 유틸리티 함수들
# ==============================================================================
def _normalize_code(value) -> str | None:
    if pd.isna(value): return None
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text or None

def _map_item_codes(df: pd.DataFrame) -> pd.DataFrame:
    normalized_map = {_normalize_code(code): name for code, name in ITEM_CODE_MAP.items()}
    rename_map = {}
    for col in df.columns:
        normalized = _normalize_code(col)
        if normalized and normalized in normalized_map:
            rename_map[col] = normalized_map[normalized]
    
    if not rename_map: return df
    mapped = df.rename(columns=rename_map)
    for col in rename_map.values():
        mapped[col] = pd.to_numeric(mapped[col], errors="coerce")
    return mapped

def load_dataguide_excel(path: str | Path) -> pd.DataFrame:
    # 1. 헤더 파싱
    raw = pd.read_excel(path, header=None)
    item_row_idx = None
    for i in range(50):
        row_str = raw.iloc[i].astype(str).values
        if any("I3100" in s for s in row_str):
            item_row_idx = i
            break
            
    if item_row_idx is None: raise SystemExit("Item row not found.")
    
    # 2. 데이터 로드
    raw.columns = raw.iloc[item_row_idx]
    data_start = item_row_idx + 1
    for i in range(item_row_idx+1, item_row_idx+50):
        try:
            dt = pd.to_datetime(raw.iloc[i, 0])
            if dt.year > 1900:
                data_start = i
                break
        except: continue
            
    df = raw.iloc[data_start:].copy()
    
    # 3. 컬럼 정리
    cols = []
    for c in df.columns:
        norm = _normalize_code(c)
        cols.append(norm if norm else "unknown")
    df.columns = cols
    
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    
    # 주말 제거
    df = df[df.index.dayofweek < 5]
    df = _map_item_codes(df)
    
    return df

def run_alpha_factor_testing(df: pd.DataFrame, params: Params) -> tuple:
    df = df.copy()
    
    # 1. 갭 계산 (Target)
    df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
    
    # 2. 팩터 계산
    if "turnover" not in df.columns:
        df["turnover"] = df["close"] * 1000 
    
    # 거래대금 5일 평균으로 정규화
    turnover_ma = df["turnover"].rolling(5).mean()
    df["priv_fund_ratio"] = df["net_priv_fund"] / turnover_ma
    
    # 3. 랭크 산출 (0.0 ~ 1.0)
    df["factor_rank"] = df["priv_fund_ratio"].rolling(window=params.rolling_window).rank(pct=True)
    
    # 4. 시그널 생성
    # 매도폭탄(하위 10%) -> Long
    long_signal = df["factor_rank"] < params.buy_threshold
    # 매수폭탄(상위 10%) -> Short
    short_signal = df["factor_rank"] > params.sell_threshold
    
    # 5. 포지션 (오늘 시그널 -> 내일 아침 갭 수익)
    # shift(1) 필수: 오늘 장마감 후 판단 -> 내일 시가 갭 매매
    df["position"] = (long_signal.astype(int) - short_signal.astype(int)).shift(1).fillna(0)
    
    # 6. 수익률 계산
    df["strategy_ret"] = df["position"] * df["gap"]
    trades = df["position"].abs()
    df["strategy_net"] = df["strategy_ret"] - (trades * params.cost)
    
    # 7. 누적 수익
    df["equity"] = (1 + df["strategy_net"].fillna(0)).cumprod()
    
    backtest = df[["gap", "priv_fund_ratio", "factor_rank", "position", "strategy_ret", "strategy_net", "equity"]]
    
    return df, {}, backtest