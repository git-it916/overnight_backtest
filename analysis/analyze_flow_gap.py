import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from statsmodels.stats.outliers_influence import variance_inflation_factor

# ==============================================================================
# 0. 설정 및 한글 폰트
# ==============================================================================
DATA_PATH = Path(r"C:\Users\10845\OneDrive - 이지스자산운용\문서\mkf2000_raw.xlsx")

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ==============================================================================
# 1. 데이터 로드 및 전처리 함수 (헤더 자동 탐색 포함)
# ==============================================================================
def load_and_preprocess(path):
    print("엑셀 데이터를 로딩 중입니다... (시간이 조금 걸립니다)")
    
    # 1. 'Item' 행 찾기 로직 (이전 수정사항 반영)
    raw = pd.read_excel(path, header=None)
    item_row_idx = None
    for i, row in raw.iterrows():
        # 행을 문자열로 변환해 'I3...' 코드가 있는지 검사
        row_str = row.astype(str).values
        if any('I3100' in s for s in row_str):
            item_row_idx = i
            break
            
    if item_row_idx is None:
        raise ValueError("유효한 Item 코드가 있는 헤더를 찾을 수 없습니다.")

    # 2. 데이터 파싱
    # Item 행을 컬럼명으로 지정
    raw.columns = raw.iloc[item_row_idx]
    # 데이터는 Item 행 + 2 (Frequency 행 건너뜀) 부터 시작한다고 가정
    df = raw.iloc[item_row_idx + 2:].copy()
    
    # 첫 번째 컬럼을 날짜로 지정
    df = df.rename(columns={df.columns[0]: 'date'})
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).set_index('date').sort_index()

    # 숫자형 변환 (Object -> Float)
    df = df.apply(pd.to_numeric, errors='coerce')

    return df

# ==============================================================================
# 2. 수급 팩터 매핑 및 생성
# ==============================================================================
def engineer_features(df):
    print("팩터 엔지니어링 및 정규화 진행 중...")
    
    # 주요 컬럼 매핑 (MKF2000 / DataGuide 표준 코드 기준)
    # 엑셀 헤더에 있는 코드들을 사람이 읽기 쉬운 이름으로 바꿉니다.
    col_map = {
        'I31000010F': 'open',
        'I31000040F': 'close',
        'I310000600': 'turnover',  # 거래대금
        
        # --- 수급 데이터 (Net Buy Amount) ---
        'I310023132': 'Net_Foreign',      # 외국인계
        'I310020032': 'Net_Inst',         # 기관계
        'I310020732': 'Net_Individual',   # 개인
        'I310020632': 'Net_Pension',      # 연기금
        'I310020132': 'Net_FinInvest',    # 금융투자
        'I310020332': 'Net_Insure',       # 보험
        'I310020432': 'Net_InvTrust',     # 투신
        'I310020532': 'Net_Bank',         # 은행
        'I310021132': 'Net_RegForeign',   # 등록외국인
        'I310020932': 'Net_PrivFund',     # 사모펀드
        'I310024132': 'Net_Nation',       # 국가/지자체
    }
    
    # 매핑 적용
    df = df.rename(columns=col_map)
    
    # 필수 컬럼 확인
    if 'turnover' not in df.columns:
        df['turnover'] = df['close'] * df['I31000050F'] # 거래량 코드가 있다면 대체 계산

    # Target 생성 (다음날 시가 갭)
    # T일 종가 진입 -> T+1일 시가 청산 수익률
    df['Next_Gap'] = (df['open'].shift(-1) - df['close']) / df['close']

    # Factor 생성: 거래대금 대비 순매수 비중 (Normalized Flow)
    # 금액 그 자체보다는 "시장 규모 대비 얼마나 샀는지"가 중요함
    flow_cols = [c for c in df.columns if c.startswith('Net_')]
    
    for col in flow_cols:
        # 거래대금의 이동평균(5일)을 사용하여 분모 안정화
        turnover_ma = df['turnover'].rolling(5).mean().replace(0, np.nan)
        df[f'Ratio_{col}'] = df[col] / turnover_ma

    return df, [f'Ratio_{c}' for c in flow_cols]

# ==============================================================================
# 3. 분석 및 시각화 (IC, VIF, Quantile)
# ==============================================================================
def analyze_factors(df, factor_cols):
    analysis_df = df.dropna(subset=['Next_Gap'] + factor_cols).copy()
    
    print("\n" + "="*50)
    print(f" [1] 상관관계(IC) 분석 (데이터 {len(analysis_df)}일)")
    print("="*50)
    
    # 1. IC (Information Coefficient) 계산
    ic_series = analysis_df[factor_cols].corrwith(analysis_df['Next_Gap'])
    ic_df = ic_series.to_frame(name='IC').sort_values(by='IC', key=abs, ascending=False)
    
    print(ic_df)
    
    # IC 시각화
    plt.figure(figsize=(10, 6))
    colors = ['red' if x > 0 else 'blue' for x in ic_df['IC']]
    ic_df['IC'].plot(kind='barh', color=colors)
    plt.title("수급 주체별 다음날 갭(Gap)과의 상관관계 (IC)")
    plt.axvline(0, color='black', linewidth=0.8)
    plt.grid(axis='x', linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.show()

    print("\n" + "="*50)
    print(" [2] 다중공선성(VIF) 검증")
    print("="*50)
    print("※ VIF > 5~10 이면 변수 간 중복(공선성)이 심해 신뢰도가 떨어짐")
    
    # VIF 계산
    X = analysis_df[factor_cols]
    vif_data = pd.DataFrame()
    vif_data["Feature"] = X.columns
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    vif_data = vif_data.sort_values(by="VIF", ascending=False)
    print(vif_data)

    print("\n" + "="*50)
    print(f" [3] Best Factor ({ic_df.index[0]}) 심층 분석")
    print("="*50)
    
    best_factor = ic_df.index[0]
    
    # 10분위 분석
    analysis_df['Group'] = pd.qcut(analysis_df[best_factor], 10, labels=False)
    grp_ret = analysis_df.groupby('Group')['Next_Gap'].mean() * 100 # %

    plt.figure(figsize=(10, 6))
    colors = ['blue' if x < 0 else 'red' for x in grp_ret]
    grp_ret.plot(kind='bar', color=colors, alpha=0.7)
    plt.title(f"[{best_factor}] 10분위별 다음날 갭 수익률 평균 (%)")
    plt.xlabel("수급 강도 (0=매도상위, 9=매수상위)")
    plt.ylabel("평균 갭 (%)")
    plt.axhline(0, color='black')
    plt.show()

# ==============================================================================
# 메인 실행
# ==============================================================================
if __name__ == "__main__":
    try:
        # 1. 로드
        df_raw = load_and_preprocess(DATA_PATH)
        
        # 2. 팩터 생성
        df_feat, factor_list = engineer_features(df_raw)
        
        # 3. 분석
        analyze_factors(df_feat, factor_list)
        
    except Exception as e:
        print(f"오류 발생: {e}")