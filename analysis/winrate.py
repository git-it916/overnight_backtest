from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parents[1] / "database"
df = pd.read_csv(DATA_DIR / "features_output.csv", index_col=0, parse_dates=True)

# 갭 크기별 구간 나누기
df['gap_rank'] = pd.qcut(df['gap'], 5, labels=["Very Low", "Low", "Mid", "High", "Very High"])

# 구간별 '장중 고가 도달(open_to_high)' 평균 확인
summary = df.groupby('gap_rank')['open_to_high'].mean()
print(summary)

# 시각화
summary.plot(kind='bar', title="Average Open-to-High Return by Gap Size")
plt.show()
