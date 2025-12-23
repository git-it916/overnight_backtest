import pandas as pd
from pathlib import Path
import shutil

# ==============================================================================
# 파일 경로 설정 (사용자 환경)
# ==============================================================================
FILE_PATH = Path(r"C:\Users\10845\OneDrive - 이지스자산운용\문서\mkf2000_raw.xlsx")
BACKUP_PATH = FILE_PATH.with_name(f"{FILE_PATH.stem}_backup_final{FILE_PATH.suffix}")

def clean_data_keep_headers():
    if not FILE_PATH.exists():
        print(f"오류: 파일을 찾을 수 없습니다. ({FILE_PATH})")
        return

    print("1. 데이터 로드 중... (헤더 없음 옵션)")
    # header=None으로 읽어야 첫 줄부터 모든 내용을 데이터처럼 다룹니다.
    df_raw = pd.read_excel(FILE_PATH, header=None)
    
    # --------------------------------------------------------------------------
    # 2. '헤더 영역'과 '데이터 영역' 정교하게 분리하기
    # --------------------------------------------------------------------------
    header_end_idx = None
    
    # 위에서부터 훑으며 'Frequency'나 'Item Name' 같은 키워드가 있는 마지막 줄 찾기
    # 보통 DataGuide 파일은 데이터 시작 직전에 'Frequency' 행이 있음
    for i in range(30):
        row_values = df_raw.iloc[i].astype(str).values
        # 행 안에 'Frequency'나 'DAILY' 같은 단어가 있으면 헤더의 일부로 간주
        if any("Frequency" in s for s in row_values) or any("DAILY" in s for s in row_values):
            header_end_idx = i
    
    if header_end_idx is None:
        print("⚠️ 경고: 'Frequency' 행을 찾지 못했습니다. 날짜 기준으로 다시 찾습니다.")
        # 차선책: 날짜가 처음 나오는 행 바로 전까지를 헤더로 설정
        for i in range(30):
            try:
                dt = pd.to_datetime(df_raw.iloc[i, 0])
                if not pd.isna(dt) and dt.year > 1900:
                    header_end_idx = i - 1
                    break
            except:
                continue

    if header_end_idx is None:
        print("오류: 데이터 구조를 파악할 수 없습니다.")
        return

    # 데이터 시작 행은 헤더 끝 다음 줄
    data_start_idx = header_end_idx + 1
    
    print(f"   - 헤더(메타데이터) 끝 위치: {header_end_idx}행")
    print(f"   - 실제 데이터 시작 위치: {data_start_idx}행")

    # --------------------------------------------------------------------------
    # 3. 분리 및 주말 삭제
    # --------------------------------------------------------------------------
    # [헤더 보호] 0행 ~ 헤더 끝 행까지 잘라내기
    df_header = df_raw.iloc[:data_start_idx].copy()
    
    # [데이터 필터링] 데이터 시작 행 ~ 끝까지
    df_data = df_raw.iloc[data_start_idx:].copy()
    
    print(f"   - 헤더 행 개수: {len(df_header)}")
    print(f"   - 원본 데이터 행 개수: {len(df_data)}")

    # 첫 번째 컬럼을 날짜로 변환
    dates = pd.to_datetime(df_data.iloc[:, 0], errors='coerce')
    
    # 조건: 날짜가 유효하고(NaT 아님) AND 평일(0~4) 인 경우만 True
    # 토(5), 일(6)은 False -> 삭제됨
    valid_mask = (dates.notna()) & (dates.dt.dayofweek < 5)
    
    df_data_clean = df_data[valid_mask]
    
    removed_count = len(df_data) - len(df_data_clean)
    print(f"3. 정제 결과: {removed_count}개의 주말(토/일) 데이터가 삭제되었습니다.")

    if removed_count == 0:
        print("   (참고: 이미 정제되었거나, 삭제할 주말 데이터가 없습니다.)")

    # --------------------------------------------------------------------------
    # 4. 합치기 및 저장
    # --------------------------------------------------------------------------
    # 헤더 블록 + 정제된 데이터 블록 합체
    df_final = pd.concat([df_header, df_data_clean])

    # 백업
    shutil.copy(FILE_PATH, BACKUP_PATH)
    print(f"   - 백업 파일 생성됨: {BACKUP_PATH.name}")

    print("4. 파일 저장 중...")
    # index=False, header=False 필수! (이미 df_header 안에 헤더 내용이 들어있으므로)
    df_final.to_excel(FILE_PATH, index=False, header=False)
    print("완료! 헤더는 살리고 주말만 삭제했습니다.")

if __name__ == "__main__":
    clean_data_keep_headers()