"""
crawler.py
KOSPI 지수 + 개별 종목 데이터 수집 및 CSV 누적 저장 모듈

핵심 원칙:
  - CSV에 raw close 전체를 저장 (ma200 계산 전 데이터 포함)
  - ma200 계산은 항상 전체 데이터로 수행
  - GitHub Actions 환경에서도 누적 데이터 유지
"""

import os
import logging
from datetime import datetime, timedelta

import pandas as pd
import FinanceDataReader as fdr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOOKBACK_DAYS = 300

TARGETS = {
    "kospi": {"ticker": "KS11",   "name": "KOSPI",     "type": "index"},
    "sec":   {"ticker": "005930", "name": "삼성전자",   "type": "stock"},
    "hynix": {"ticker": "000660", "name": "SK하이닉스", "type": "stock"},
    "sem":   {"ticker": "009150", "name": "삼성전기",   "type": "stock"},
}

# raw close만 저장하는 CSV (ma200 계산용 원시 데이터)
def raw_csv_path(key: str) -> str:
    return os.path.join(DATA_DIR, f"{key}_raw.csv")

# 지표 포함 최종 CSV
def csv_path(key: str) -> str:
    return os.path.join(DATA_DIR, f"{key}_history.csv")


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _calc_indicators(close_series: pd.Series) -> pd.DataFrame:
    """종가 시리즈 → MA + 이격도 계산. ma200 계산 가능한 행만 반환."""
    df = pd.DataFrame({"close": close_series})
    df["ma50"]       = df["close"].rolling(50,  min_periods=50).mean().round(2)
    df["ma200"]      = df["close"].rolling(200, min_periods=200).mean().round(2)
    df["distance50"]  = (df["close"] / df["ma50"]  * 100).round(2)
    df["distance200"] = (df["close"] / df["ma200"] * 100).round(2)
    df["close"]      = df["close"].round(2)
    return df.dropna(subset=["ma200"])


def load_raw(key: str) -> pd.DataFrame | None:
    """raw close CSV 로드."""
    path = raw_csv_path(key)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        logger.info(f"[{key}] raw CSV 로드: {len(df)}행")
        return df
    except Exception as e:
        logger.warning(f"[{key}] raw CSV 읽기 실패: {e}")
        return None


def load_existing(key: str) -> pd.DataFrame | None:
    """지표 포함 최종 CSV 로드."""
    path = csv_path(key)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        logger.info(f"[{key}] 기존 CSV 로드: {len(df)}행")
        return df
    except Exception as e:
        logger.warning(f"[{key}] CSV 읽기 실패: {e}")
        return None


def fetch_one(key: str, meta: dict, start: str) -> pd.DataFrame:
    """단일 종목 원시 종가 수집."""
    ticker = meta["ticker"]
    name   = meta["name"]
    logger.info(f"[{key}] {name} ({ticker}) 수집 시작: {start} ~")
    try:
        raw = fdr.DataReader(ticker, start)
        if raw.empty:
            raise ValueError("빈 데이터")
        col = "Close" if "Close" in raw.columns else raw.columns[0]
        series = raw[col].copy()
        series.index = pd.to_datetime(series.index)
        series.index.name = "date"
        series.name = "close"
        logger.info(f"[{key}] 수집 완료: {len(series)}행 "
                    f"({series.index[0].date()} ~ {series.index[-1].date()})")
        return series.to_frame()
    except Exception as e:
        logger.error(f"[{key}] 수집 실패: {e}")
        raise


def collect_one(key: str, meta: dict) -> pd.DataFrame:
    """
    단일 종목 수집 → raw CSV 누적 → 지표 계산 → history CSV 저장.

    raw CSV에 전체 종가를 누적 보관하기 때문에
    GitHub Actions 환경에서도 ma200 계산에 필요한 데이터가 항상 확보됨.
    """
    # 1. raw CSV 로드 (기존 누적 데이터)
    existing_raw = load_raw(key)

    # 2. 수집 시작일 결정
    if existing_raw is not None and not existing_raw.empty:
        last = existing_raw.index.max()
        # 마지막 날 다음날부터 수집 (중복 방지 + 당일 업데이트)
        start = (last - timedelta(days=5)).strftime("%Y-%m-%d")
    else:
        # 최초: 2년치 수집
        start = (datetime.today() - timedelta(days=365 * 2 + 100)).strftime("%Y-%m-%d")

    # 3. 신규 데이터 수집
    new_raw = fetch_one(key, meta, start)

    # 4. raw 데이터 병합 (전체 누적)
    if existing_raw is not None and not existing_raw.empty:
        combined_raw = pd.concat([existing_raw[["close"]], new_raw]).sort_index()
        combined_raw = combined_raw[~combined_raw.index.duplicated(keep="last")]
    else:
        combined_raw = new_raw.copy()

    # 5. raw CSV 저장 (지표 없이 순수 종가만)
    combined_raw.index.name = "date"
    combined_raw.to_csv(raw_csv_path(key), date_format="%Y-%m-%d")
    logger.info(f"[{key}] raw CSV 저장: {len(combined_raw)}행")

    # 6. 전체 데이터로 지표 계산
    result = _calc_indicators(combined_raw["close"])
    result.index.name = "date"
    result.to_csv(csv_path(key), date_format="%Y-%m-%d")
    logger.info(f"[{key}] history CSV 저장: {len(result)}행")

    return result


def collect_all() -> dict[str, pd.DataFrame]:
    ensure_data_dir()
    results: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    for key, meta in TARGETS.items():
        try:
            df = collect_one(key, meta)
            results[key] = df
        except Exception as e:
            logger.error(f"[{key}] 수집 건너뜀: {e}")
            errors.append(key)
            existing = load_existing(key)
            if existing is not None:
                results[key] = existing

    if errors:
        logger.warning(f"수집 실패 종목: {errors}")
    logger.info(f"전체 수집 완료: {len(results)}/{len(TARGETS)}개")
    return results


if __name__ == "__main__":
    data = collect_all()
    for key, df in data.items():
        name = TARGETS[key]["name"]
        print(f"\n[{name}] 최근 3일:")
        print(df.tail(3).to_string())
