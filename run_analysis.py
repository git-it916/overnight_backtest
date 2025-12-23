from pathlib import Path

from overnight_alpha import Params, load_dataguide_excel, run_alpha_factor_testing


DATA_PATH = Path(
    r"C:\Users\10845\OneDrive - 이지스자산운용\문서\mkf2000_raw.xlsx"
)


def main() -> None:
    df = load_dataguide_excel(DATA_PATH)

    params = Params(
        gap_abs_max=0.01,
        take_profit_opening=0.003,
        stop_opening=0.0015,
        dir_ratio_thresh=0.60,
        cost=0.0002,
        optimistic_fill=True,
    )

    df_features, heatmaps, backtest = run_alpha_factor_testing(df, params)

    print(backtest[["direction", "pnl_overnight", "pnl_opening", "pnl_net", "equity"]])

    df_features.to_csv("features_output.csv")
    backtest.to_csv("backtest_output.csv")

    _ = heatmaps


if __name__ == "__main__":
    main()
