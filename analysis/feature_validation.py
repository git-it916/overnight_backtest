from pathlib import Path

import pandas as pd
from scipy import stats

# 1. 데이터 로드 (분석 결과 파일)
# 파일 경로가 맞는지 확인해주세요.
DATA_DIR = Path(__file__).resolve().parents[1] / "database"
file_path = DATA_DIR / "features_output.csv"

try:
    df = pd.read_csv(file_path, index_col=0)
    print(f"데이터 로드 성공: 총 {len(df)}일의 데이터가 있습니다.\n")

    # 2. 검증할 변수 쌍 설정
    # (Gap vs Open_to_High), (Gap vs Dir_Ratio_Long)
    pairs = [
        ("gap", "open_to_high"),
        ("gap", "dir_ratio_long")
    ]

    print(f"{'Variable 1':<15} {'Variable 2':<15} {'Corr(r)':<10} {'P-value':<15} {'Result'}")
    print("-" * 70)

    for v1, v2 in pairs:
        # 결측치 제거 후 계산 (중요)
        clean_data = df[[v1, v2]].dropna()
        
        # 피어슨 상관계수 및 P-value 계산
        r, p_value = stats.pearsonr(clean_data[v1], clean_data[v2])
        
        # 결과 해석
        significance = "유의함(Significant)" if p_value < 0.05 else "유의하지 않음"
        
        print(f"{v1:<15} {v2:<15} {r:<10.4f} {p_value:<15.4e} {significance}")

    print("\n[해석 가이드]")
    print("- P-value < 0.05: 통계적으로 유의미한 관계임 (우연이 아님)")
    print("- P-value < 0.01: 매우 강력한 관계임")
    
except FileNotFoundError:
    print(
        "오류: 'features_output.csv' 파일을 찾을 수 없습니다. "
        "run_analysis.py를 먼저 실행했는지 확인해주세요."
    )
