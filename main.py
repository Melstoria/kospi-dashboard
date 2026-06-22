"""
main.py
KOSPI Market Dashboard — 메인 실행 파일
"""

import argparse
import logging
import os
import sys
import time
import webbrowser
from datetime import datetime

import schedule

from crawler import collect_all
from dashboard import render_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dashboard_run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "dashboard.html")


def run_pipeline(open_browser: bool = False) -> bool:
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("KOSPI Dashboard Pipeline 시작")
    logger.info("=" * 60)
    try:
        # output 폴더 없으면 자동 생성 (GitHub Actions 환경 대비)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        logger.info("[1/3] 전체 데이터 수집 중...")
        all_data = collect_all()
        if not all_data:
            logger.error("데이터 수집 실패. 중단.")
            return False
        for key, df in all_data.items():
            logger.info(f"      [{key}] {len(df)}거래일 (최신: {df.index[-1].date()})")

        logger.info("[2/3] 지표 계산 완료 (MA50 / MA200 / 이격도)")

        logger.info("[3/3] HTML 대시보드 생성 중...")
        output_path = render_dashboard(all_data, OUTPUT_HTML)
        logger.info(f"      생성 완료 → {output_path}")

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"Pipeline 완료 ({elapsed:.1f}초)")
        logger.info("=" * 60)

        if open_browser:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")
        return True

    except Exception as e:
        logger.exception(f"Pipeline 오류: {e}")
        return False


def run_scheduler():
    schedule.every().day.at("16:05").do(lambda: run_pipeline(open_browser=False))
    logger.info("스케줄러 시작 — 매일 16:05 자동 실행 (Ctrl+C로 종료)")
    run_pipeline(open_browser=False)
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="KOSPI Market Dashboard")
    parser.add_argument("--watch",      action="store_true", help="매일 16:05 자동 실행")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 오픈 비활성화")
    args = parser.parse_args()

    if args.watch:
        run_scheduler()
    else:
        success = run_pipeline(open_browser=not args.no_browser)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
