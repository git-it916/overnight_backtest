from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parents[1] / "database"
df = pd.read_csv(DATA_DIR / "features_output.csv", index_col=0, parse_dates=True)

# 주요 지표 간 상관관계
corr = df[['gap', 'ret_1d', 'open_to_high', 'dir_ratio_long']].corr()

plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
plt.title("Feature Correlations")
plt.show()
