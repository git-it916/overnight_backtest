from pathlib import Path
from overnight_alpha import Params, load_dataguide_excel, run_alpha_factor_testing

# 파일 경로 (사용자분 경로 그대로 유지)
DATA_PATH = Path(r"C:\Users\10845\OneDrive - 이지스자산운용\문서\mkf2000_raw.xlsx")
OUTPUT_DIR = Path(__file__).resolve().parent / "database"

def main() -> None:
    print("1. 데이터를 불러오는 중입니다...")
    df = load_dataguide_excel(DATA_PATH)

    print("2. 전략 파라미터를 설정합니다...")
    # [수정] 오직 필요한 변수 4개만 넣었습니다. (오류 원인 원천 차단)
    params = Params(
        rolling_window=60,   # 60일 랭크
        buy_threshold=0.10,  # 하위 10% -> 매수
        sell_threshold=0.90, # 상위 10% -> 매도
        cost=0.0015          # 수수료
    )

    print("3. 백테스트를 실행합니다...")
    df_features, _, backtest = run_alpha_factor_testing(df, params)
    
    print("\n[최근 20일 거래 내역 및 수익률]")
    print(backtest[["position", "strategy_net", "equity"]].tail(20))
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    df_features.to_csv(OUTPUT_DIR / "features_output.csv")
    backtest.to_csv(OUTPUT_DIR / "backtest_output.csv")
    output_file = OUTPUT_DIR / "final_strategy_result.csv"
    backtest.to_csv(output_file)
    print(f"\n[완료] 결과가 '{output_file}'에 저장되었습니다.")

if __name__ == "__main__":
    main()
