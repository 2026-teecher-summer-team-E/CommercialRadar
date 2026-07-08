"""인제스천 transformer 테스트용 raw 응답 팩토리.

각 팩토리는 해당 Pydantic 모델의 alias(서울/R-ONE API의 대문자 필드명) 그대로를
키로 갖는 dict를 반환한다. `**overrides`로 개별 필드를 덮어쓰고, 필드 누락 케이스는
반환된 dict에서 `del`로 제거해 만든다.

fixture가 아니라 일반 헬퍼 함수인 이유: 파라미터 오버라이드가 쉽고, 한 테스트에서
여러 변형을 만들 수 있기 때문이다.
"""


def commercial_raw(**overrides) -> dict:
    """서울 상권영역(TbgisTrdarRelm) raw 1건. 중심점 좌표/면적은 무시 대상(extra)."""
    return {
        "TRDAR_CD": "1000001",
        "TRDAR_CD_NM": "명동거리",
        "TRDAR_SE_CD_NM": "발달상권",
        "SIGNGU_CD": "11140",
        "SIGNGU_CD_NM": "중구",
        "ADSTRD_CD": "11140550",
        "ADSTRD_CD_NM": "명동",
        # 아래는 transformer가 무시해야 하는 extra 필드
        "XCNTS_VALUE": "198000.0",
        "YDNTS_VALUE": "451000.0",
        "RELM_AR": "12345.6",
    } | overrides


def selng_raw(**overrides) -> dict:
    """추정매출(VwsmTrdarSelngQq) raw 1건. TMZON_*는 11~14시가 최대(peak)."""
    return {
        "TRDAR_CD": "1000001",
        "STDR_YYQU_CD": "20254",
        "SVC_INDUTY_CD": "CS100001",
        "SVC_INDUTY_CD_NM": "한식음식점",
        "THSMON_SELNG_AMT": "5000000",
        "THSMON_SELNG_CO": "1200",
        "TMZON_00_06_SELNG_AMT": "100",
        "TMZON_06_11_SELNG_AMT": "200",
        "TMZON_11_14_SELNG_AMT": "900",
        "TMZON_14_17_SELNG_AMT": "300",
        "TMZON_17_21_SELNG_AMT": "400",
        "TMZON_21_24_SELNG_AMT": "500",
    } | overrides


def stor_raw(**overrides) -> dict:
    """점포(VwsmTrdarStorQq) raw 1건. 추정매출과 최신 분기가 다를 수 있다."""
    return {
        "TRDAR_CD": "1000001",
        "STDR_YYQU_CD": "20261",
        "SVC_INDUTY_CD": "CS100001",
        "SVC_INDUTY_CD_NM": "한식음식점",
        "STOR_CO": "50",
        "OPBIZ_RT": "10.5",
        "CLSBIZ_RT": "3.2",
    } | overrides


def rent_raw(**overrides) -> dict:
    """R-ONE 상가임대료(WRTTIME=202601=2026-Q1) raw 1건. 서울 말단 상권·임대료 항목."""
    return {
        "CLS_NM": "명동",
        "CLS_FULLNM": "서울>도심>명동",
        "ITM_NM": "임대료",
        "DTA_VAL": "50.5",
        "WRTTIME_IDTFR_ID": "202601",
    } | overrides


def foreign_raw(**overrides) -> dict:
    """생활인구 세 서비스 공통 raw 1건 (STDR_DE_ID=2024-01-01=월요일).

    TOT_LVPOP_CO는 API가 문자열로 반환하므로 문자열로 둔다(coerce 검증용).
    """
    return {
        "STDR_DE_ID": "20240101",
        "TMZON_PD_SE": "12",
        "ADSTRD_CODE_SE": "11140550",
        "TOT_LVPOP_CO": "100.0",
    } | overrides


def population_raw(**overrides) -> dict:
    """유동인구(VwsmTrdarFlpopQq) raw 1건.

    heatmap(시간대·요일)과 timeseries(총계·성별·연령) 두 transformer가 같은 raw를
    쓰므로 두 스키마의 필드를 모두 포함한다.
    """
    return {
        "TRDAR_CD": "1000001",
        "STDR_YYQU_CD": "20241",
        "TOT_FLPOP_CO": "1000",
        # 시간대 6개
        "TMZON_00_06_FLPOP_CO": "10",
        "TMZON_06_11_FLPOP_CO": "20",
        "TMZON_11_14_FLPOP_CO": "30",
        "TMZON_14_17_FLPOP_CO": "40",
        "TMZON_17_21_FLPOP_CO": "50",
        "TMZON_21_24_FLPOP_CO": "60",
        # 요일 7개
        "MON_FLPOP_CO": "1",
        "TUES_FLPOP_CO": "2",
        "WED_FLPOP_CO": "3",
        "THUR_FLPOP_CO": "4",
        "FRI_FLPOP_CO": "5",
        "SAT_FLPOP_CO": "6",
        "SUN_FLPOP_CO": "7",
        # 성별 2개
        "ML_FLPOP_CO": "600",
        "FML_FLPOP_CO": "400",
        # 연령대 6개
        "AGRDE_10_FLPOP_CO": "100",
        "AGRDE_20_FLPOP_CO": "200",
        "AGRDE_30_FLPOP_CO": "300",
        "AGRDE_40_FLPOP_CO": "150",
        "AGRDE_50_FLPOP_CO": "150",
        "AGRDE_60_ABOVE_FLPOP_CO": "100",
    } | overrides
