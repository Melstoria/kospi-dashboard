"""
crawler.py
KOSPI 지수 + 개별 종목 데이터 수집 및 CSV 누적 저장 모듈

지원 종목:
  - KS11     : KOSPI 종합지수 (KrxIndexReaderCache → GitHub raw 캐시)
  - 005930   : 삼성전자
  - 000660   : SK하이닉스
  - 009150   : 삼성전기
  (개별 종목은 FinanceDataReader NAVER 소스 사용 — 로컬 실행 필수)
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

DATA_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOOKBACK_DAYS = 300  # 200일선 계산을 위한 여유 기간

# ─── 수집 대상 정의 ──────────────────────────────────────────────────────────
# ticker : FDR에 넘길 심볼 코드
# name   : 표시 이름
# type   : 'index' | 'stock'  (수집 방식 분기용)
TARGETS = {
    "kospi":   {"ticker": "KS11",   "name": "KOSPI",     "type": "index"},
    "sec":     {"ticker": "005930", "name": "삼성전자",   "type": "stock"},
    "hynix":   {"ticker": "000660", "name": "SK하이닉스", "type": "stock"},
    "sem":     {"ticker": "009150", "name": "삼성전기",   "type": "stock"},
}


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def csv_path(key: str) -> str:
    return os.path.join(DATA_DIR, f"{key}_history.csv")


def _calc_indicators(close_series: pd.Series) -> pd.DataFrame:
    """
    종가 시리즈로부터 MA·이격도를 계산하여 DataFrame 반환.
    ma200이 계산 불가한 초기 구간은 제거.
    """
    df = pd.DataFrame({"close": close_series})
    df["ma50"]      = df["close"].rolling(window=50,  min_periods=50).mean().round(2)
    df["ma200"]     = df["close"].rolling(window=200, min_periods=200).mean().round(2)
    df["distance50"]  = (df["close"] / df["ma50"]  * 100).round(2)
    df["distance200"] = (df["close"] / df["ma200"] * 100).round(2)
    df["close"]     = df["close"].round(2)
    return df.dropna(subset=["ma200"])


def load_existing(key: str) -> pd.DataFrame | None:
    path = csv_path(key)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        logger.info(f"[{key}] 기존 CSV 로드: {len(df)}행")
        return df
    except Exception as e:
        logger.warning(f"[{key}] CSV 읽기 실패 (재생성): {e}")
        return None


def _start_date(existing: pd.DataFrame | None) -> str:
    if existing is not None and not existing.empty:
        last = existing.index.max()
        return (last - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    return (datetime.today() - timedelta(days=365 * 2 + 100)).strftime("%Y-%m-%d")


def fetch_one(key: str, meta: dict, start: str) -> pd.DataFrame:
    """
    단일 종목/지수의 원시 종가 시리즈 수집.
    Returns: close 컬럼만 있는 DatetimeIndex DataFrame
    """
    ticker = meta["ticker"]
    name   = meta["name"]
    logger.info(f"[{key}] {name} ({ticker}) 수집 시작: {start} ~")
    try:
        raw = fdr.DataReader(ticker, start)
        if raw.empty:
            raise ValueError("빈 데이터")
        # 컬럼 이름 정규화 (Close / close 혼용 대응)
        col = "Close" if "Close" in raw.columns else raw.columns[0]
        series = raw[col].copy()
        series.index = pd.to_datetime(series.index)
        series.index.name = "date"
        series.name = "close"
        logger.info(f"[{key}] 수집 완료: {len(series)}행 ({series.index[0].date()} ~ {series.index[-1].date()})")
        return series.to_frame()
    except Exception as e:
        logger.error(f"[{key}] 수집 실패: {e}")
        raise


def collect_one(key: str, meta: dict) -> pd.DataFrame:
    """
    단일 종목 수집 → 지표 계산 → CSV 저장 → DataFrame 반환.
    증분 업데이트 지원.
    """
    existing = load_existing(key)
    start    = _start_date(existing)

    raw = fetch_one(key, meta, start)

    # ── 기존 데이터와 병합 ────────────────────────────────────────
    if existing is not None and not existing.empty:
        old_close = existing[["close"]].copy()
        combined  = pd.concat([old_close, raw]).sort_index()
        combined  = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = raw.copy()

    # ── 지표 계산 ─────────────────────────────────────────────────
    result = _calc_indicators(combined["close"])
    result.index.name = "date"
    result.to_csv(csv_path(key), date_format="%Y-%m-%d")
    logger.info(f"[{key}] CSV 저장: {csv_path(key)} ({len(result)}행)")
    return result


def collect_all() -> dict[str, pd.DataFrame]:
    """
    TARGETS에 정의된 모든 종목을 순차 수집.

    Returns:
        {key: DataFrame} — 키는 TARGETS 딕셔너리의 키와 동일
    """
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
            # 기존 CSV라도 반환
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
