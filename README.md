# KOSPI Market Dashboard

[![Update Dashboard](https://github.com/YOUR_USERNAME/kospi-dashboard/actions/workflows/update_dashboard.yml/badge.svg)](https://github.com/YOUR_USERNAME/kospi-dashboard/actions/workflows/update_dashboard.yml)

> **라이브 대시보드**: https://YOUR_USERNAME.github.io/kospi-dashboard/

코스피 지수 + 삼성전자·SK하이닉스·삼성전기 이격도 모니터링 시스템.  
GitHub Actions가 **평일 매일 16:10** 자동으로 데이터를 수집하고 대시보드를 갱신합니다.

---

## 📁 프로젝트 구조

```
kospi-dashboard/
├── .github/
│   └── workflows/
│       └── update_dashboard.yml   ← 자동화 핵심
├── data/
│   ├── kospi_history.csv          ← KOSPI 누적 데이터 (git 추적)
│   ├── sec_history.csv            ← 삼성전자
│   ├── hynix_history.csv          ← SK하이닉스
│   └── sem_history.csv            ← 삼성전기
├── docs/
│   └── index.html                 ← GitHub Pages 서빙 파일
├── templates/
│   └── dashboard.html             ← Jinja2 템플릿
├── crawler.py                     ← 데이터 수집
├── indicator.py                   ← 이격도·상태 분류
├── dashboard.py                   ← 차트·HTML 생성
├── main.py                        ← 진입점
├── requirements.txt
└── README.md
```

---

## 🚀 GitHub Pages 배포 방법 (최초 1회)

### Step 1 — 레포지토리 생성 & 업로드

```bash
# 로컬에서 실행
cd kospi-dashboard
git init
git add .
git commit -m "initial commit"

# GitHub에서 새 레포 생성 후 (YOUR_USERNAME/kospi-dashboard)
git remote add origin https://github.com/YOUR_USERNAME/kospi-dashboard.git
git branch -M main
git push -u origin main
```

### Step 2 — GitHub Pages 활성화

1. 레포 상단 **Settings** 탭 클릭
2. 왼쪽 사이드바 **Pages**
3. **Source**: `Deploy from a branch`
4. **Branch**: `main` / **Folder**: `/docs`
5. **Save** 클릭

→ 약 1~2분 후 `https://YOUR_USERNAME.github.io/kospi-dashboard/` 접속 가능

### Step 3 — Actions 권한 확인

1. **Settings** → **Actions** → **General**
2. **Workflow permissions**: `Read and write permissions` 선택
3. **Save**

---

## ⏰ 자동 업데이트 스케줄

| 항목 | 내용 |
|------|------|
| 실행 시각 | 평일(월~금) 16:10 KST |
| 소요 시간 | 약 30~60초 |
| 수동 실행 | Actions 탭 → `Update KOSPI Dashboard` → `Run workflow` |

---

## 💻 로컬 실행

```bash
pip install -r requirements.txt
python main.py              # 실행 + 브라우저 자동 오픈
python main.py --no-browser # 브라우저 없이
```

---

## 📊 이격도 기준표

| 50일 이격도 | 상태 | 의미 |
|------------|------|------|
| 130 이상 | 🔴 과열 | 단기 과매수 |
| 120 ~ 130 | 🟠 경계 | 신규 매수 자제 |
| 105 ~ 120 | 🟢 정상 | 정상 운용 |
| 105 이하 | 🔵 과열해소 | 분할 매수 고려 |

> ⚠️ 본 대시보드는 투자 참고용입니다. 최종 투자 판단의 책임은 본인에게 있습니다.
