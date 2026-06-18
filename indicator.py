"""
indicator.py
이격도 기반 상태 분류 모듈 — KOSPI + 개별 종목 공용
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ─── 이격도 임계값 (50일선 기준, 코스피·개별종목 공용) ─────────────────────
THRESHOLDS = {
    "overheat":     130,   # 과열
    "caution":      120,   # 경계
    "normal_upper": 105,   # 정상 (105 ~ 120)
    # 105 이하 = 과열해소
}

STATUS_MAP = {
    "과열":     {"label": "과열",     "color": "#FF3B30", "bg": "#FFF0EF", "en": "OVERHEAT"},
    "경계":     {"label": "경계",     "color": "#FF9500", "bg": "#FFF8EE", "en": "CAUTION"},
    "정상":     {"label": "정상",     "color": "#34C759", "bg": "#F0FAF3", "en": "NORMAL"},
    "과열해소": {"label": "과열해소", "color": "#007AFF", "bg": "#EEF5FF", "en": "COOLED"},
}


def classify_status(distance50: float) -> str:
    if pd.isna(distance50):
        return "정상"
    if distance50 >= THRESHOLDS["overheat"]:
        return "과열"
    elif distance50 >= THRESHOLDS["caution"]:
        return "경계"
    elif distance50 >= THRESHOLDS["normal_upper"]:
        return "정상"
    else:
        return "과열해소"


def get_status_meta(status: str) -> dict:
    return STATUS_MAP.get(status, STATUS_MAP["정상"])


def add_status_column(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["status"] = result["distance50"].apply(classify_status)
    return result


def get_latest_summary(df: pd.DataFrame, name: str = "KOSPI",
                       is_index: bool = True) -> dict:
    """
    카드용 최신 요약 지표.

    Args:
        df:       전처리된 DataFrame
        name:     표시 이름 (예: '삼성전자')
        is_index: True면 소수점 2자리 표시, False면 정수(원 단위)
    """
    if df.empty:
        return {}

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) >= 2 else latest

    status = classify_status(latest["distance50"])
    meta   = get_status_meta(status)

    close_change     = latest["close"] - prev["close"]
    close_change_pct = (close_change / prev["close"] * 100) if prev["close"] != 0 else 0
    d50_change       = latest["distance50"] - prev["distance50"]

    # 지수 vs 주식 표시 형식 분기
    if is_index:
        fmt_close = f"{latest['close']:,.2f}"
        fmt_chg   = f"{close_change:+,.2f}"
        fmt_ma50  = f"{latest['ma50']:,.2f}"
        fmt_ma200 = f"{latest['ma200']:,.2f}"
    else:
        fmt_close = f"{int(latest['close']):,}원"
        fmt_chg   = f"{int(close_change):+,}원"
        fmt_ma50  = f"{int(latest['ma50']):,}원"
        fmt_ma200 = f"{int(latest['ma200']):,}원"

    return {
        "name":             name,
        "date":             latest.name.strftime("%Y-%m-%d"),
        "close":            fmt_close,
        "close_raw":        latest["close"],
        "close_change":     fmt_chg,
        "close_change_pct": f"{close_change_pct:+.2f}%",
        "close_up":         close_change >= 0,
        "ma50":             fmt_ma50,
        "ma200":            fmt_ma200,
        "distance50":       f"{latest['distance50']:.2f}",
        "distance50_raw":   latest["distance50"],
        "d50_change":       f"{d50_change:+.2f}",
        "distance200":      f"{latest['distance200']:.2f}",
        "status":           status,
        "status_color":     meta["color"],
        "status_bg":        meta["bg"],
        "status_en":        meta["en"],
        "thresholds":       THRESHOLDS,
    }


def get_table_data(df: pd.DataFrame, n: int = 30,
                   is_index: bool = True) -> list[dict]:
    """
    최근 N일 테이블 데이터.

    Args:
        df:       전처리된 DataFrame
        n:        행 수
        is_index: True면 지수 형식, False면 주식(원) 형식
    """
    subset = add_status_column(df.tail(n).copy())
    subset = subset.sort_index(ascending=False)
    rows = []
    for date, row in subset.iterrows():
        meta = get_status_meta(row["status"])
        if is_index:
            close_str = f"{row['close']:,.2f}"
            ma50_str  = f"{row['ma50']:,.2f}"
        else:
            close_str = f"{int(row['close']):,}원"
            ma50_str  = f"{int(row['ma50']):,}원"
        rows.append({
            "date":       date.strftime("%Y-%m-%d"),
            "close":      close_str,
            "ma50":       ma50_str,
            "distance50": f"{row['distance50']:.2f}",
            "status":     row["status"],
            "color":      meta["color"],
            "bg":         meta["bg"],
        })
    return rows
