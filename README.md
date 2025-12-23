# overnight_backtest

## 프로젝트 목적

DAILY OHLCV + 수급 데이터를 이용해 **"t-1 조건 -> t 오프닝 알파(근사)"**를 검증하는
알파 팩터 테스트 프레임워크입니다.

## 데이터

- DataGuide 원본 엑셀을 사용합니다.
- 헤더명이 아니라 **Item 코드**로 파싱합니다.
- 분봉 없이 일봉 데이터만 사용합니다.

## 설치 및 기본 실행

```bash
pip install -r requirements.txt
python run_analysis.py
```

## 결과 파일 (자동 생성)

모든 결과는 `database/` 폴더에 저장됩니다.

- `database/features_output.csv`: 팩터/피처 계산 결과
- `database/backtest_output.csv`: 백테스트 결과(주요 PnL/지표)
- `database/final_strategy_result.csv`: 최종 전략 결과

## 파일별 설명 및 실행 코드

| 경로 | 설명 | 실행 코드 |
| --- | --- | --- |
| `run_analysis.py` | 메인 실행 스크립트. DataGuide 엑셀 로드 → 파라미터 적용 → 백테스트/피처 저장 | `python run_analysis.py` |
| `overnight_alpha.py` | 핵심 로직 모듈(데이터 파싱, 팩터/백테스트 함수) | 직접 실행하지 않음 |
| `backtest_overnight.py` | 범용 OHLCV 기반 특성/시각화 분석용 CLI | `python backtest_overnight.py <data.xlsx>` |
| `gooo.py` | DataGuide 엑셀 헤더 유지 + 주말 제거 + 백업 생성 | `python gooo.py` |
| `analysis/heatmap.py` | 피처 상관관계 히트맵 출력 | `python analysis\\heatmap.py` |
| `analysis/winrate.py` | 갭 구간별 open_to_high 평균 분석 | `python analysis\\winrate.py` |
| `analysis/feature_validation.py` | 피처 상관/유의성 검정 | `python analysis\\feature_validation.py` |
| `analysis/result.py` | 전략 성과 요약(KPI) + 차트 | `python analysis\\result.py` |
| `analysis/analyze_flow_gap.py` | 수급 팩터 IC/VIF/분위 분석 | `python analysis\\analyze_flow_gap.py` |
| `requirements.txt` | 최소 의존성 목록 | `pip install -r requirements.txt` |
| `.vscode/launch.json` | VS Code 실행 설정 | 실행 없음 |
| `.vscode/settings.json` | VS Code 환경 설정 | 실행 없음 |

## 추가 설치(분석 스크립트용)

아래 스크립트는 추가 패키지가 필요합니다.

```bash
pip install seaborn scipy statsmodels
```

## 참고 사항

- `run_analysis.py`, `analysis/analyze_flow_gap.py`, `gooo.py`는 엑셀 파일 경로가 하드코딩되어 있으니
  필요 시 파일 안의 경로를 수정하세요.
- 분석 스크립트들은 `database/` 폴더의 결과 CSV를 참조합니다. 먼저 `python run_analysis.py`를 실행하세요.
