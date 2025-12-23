from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 1. 결과 파일 로드
DATA_DIR = Path(__file__).resolve().parents[1] / "database"
file_path = DATA_DIR / "final_strategy_result.csv"

try:
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    print(f"데이터 로드 완료: {len(df)} 거래일")
except FileNotFoundError:
    print("오류: 'final_strategy_result.csv' 파일을 찾을 수 없습니다.")
    exit()

# 2. 예열 기간(Warm-up) 제외하기
# factor_rank가 계산되기 시작한(값이 있는) 시점부터 잘라냅니다.
df_clean = df.dropna(subset=['factor_rank']).copy()

if len(df_clean) == 0:
    print("오류: 아직 랭크가 계산된 데이터가 없습니다. 데이터 기간이 60일보다 짧은지 확인해보세요.")
    exit()

# 예열 기간 이후의 시작일을 기준으로 Equity(자산 곡선) 재조정 (1.0부터 시작하도록)
df_clean['equity_real'] = (1 + df_clean['strategy_net']).cumprod()

print(f"\n[분석 구간] {df_clean.index[0].date()} ~ {df_clean.index[-1].date()} (총 {len(df_clean)}일)")

# 3. 핵심 성과 지표 (KPI) 계산
total_return = (df_clean['equity_real'].iloc[-1] - 1) * 100
days = (df_clean.index[-1] - df_clean.index[0]).days
cagr = ((df_clean['equity_real'].iloc[-1]) ** (365 / days) - 1) * 100 if days > 0 else 0

# MDD (최대 낙폭) 계산
rolling_max = df_clean['equity_real'].cummax()
daily_drawdown = df_clean['equity_real'] / rolling_max - 1.0
mdd = daily_drawdown.min() * 100

# 승률 계산 (매매가 있었던 날 중 수익 난 날)
# position이 0이 아닌 날(진입한 날)만 필터링
trade_days = df_clean[df_clean['position'] != 0]
win_days = trade_days[trade_days['strategy_net'] > 0]
win_rate = (len(win_days) / len(trade_days)) * 100 if len(trade_days) > 0 else 0

print("\n" + "="*40)
print(f" 📈 전략 성과 요약 (사모펀드 역추세)")
print("="*40)
print(f"누적 수익률 (Total Return) : {total_return:>.2f}%")
print(f"연평균 수익률 (CAGR)       : {cagr:>.2f}%")
print(f"최대 낙폭 (MDD)            : {mdd:>.2f}%")
print(f"총 매매 횟수               : {len(trade_days)}회")
print(f"승률 (Win Rate)            : {win_rate:>.2f}%")
print("="*40)

# 4. 시각화 (차트 그리기)
plt.figure(figsize=(12, 8))

# (1) 누적 수익률 차트
plt.subplot(2, 1, 1)
plt.plot(df_clean.index, df_clean['equity_real'], label='Strategy Equity', color='red', linewidth=1.5)
plt.plot(df_clean.index, (1+df_clean['gap']).cumprod(), label='Benchmark (Gap Hold)', color='grey', alpha=0.3)
plt.title("Cumulative Return (Equity Curve)")
plt.legend()
plt.grid(True, alpha=0.3)

# (2) Drawdown & Position 차트
plt.subplot(2, 1, 2)
plt.fill_between(df_clean.index, daily_drawdown * 100, 0, color='blue', alpha=0.2, label='Drawdown (%)')
plt.ylabel('Drawdown (%)')

# 포지션 표시 (보조축)
ax2 = plt.gca().twinx()
ax2.plot(df_clean.index, df_clean['position'], color='black', alpha=0.3, linewidth=0.5, linestyle=':', label='Position')
ax2.set_ylabel('Position (1=Long, -1=Short)', color='black')
ax2.set_ylim(-1.5, 1.5)

plt.title("Drawdown & Positions")
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
