"""
dashboard.py  —  차트 JSON 분리 + DOMContentLoaded 렌더링 방식
Plotly CDN 타이밍 문제 해결: to_html 대신 to_json으로 데이터만 추출,
템플릿에서 DOMContentLoaded 이후 Plotly.newPlot() 일괄 호출
"""

import os
import json
import logging
import uuid
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader

from crawler import TARGETS
from indicator import (
    add_status_column,
    get_latest_summary,
    get_table_data,
    THRESHOLDS,
)

logger = logging.getLogger(__name__)

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")

# ── 색상 팔레트 ──────────────────────────────────────────────────────────────
C = {
    "kospi":  "#007AFF",
    "sec":    "#FF9500",
    "hynix":  "#AF52DE",
    "sem":    "#FF2D55",
    "ma50":   "#F59E0B",
    "ma200":  "#10B981",
    "grid":   "#E8E8ED",
    "bg":     "rgba(0,0,0,0)",
    "font":   "#1C1C1E",
    "sub":    "#6E6E73",
    "over":   "#FF3B30",
    "caut":   "#FF9500",
    "norm":   "#34C759",
    "cool":   "#007AFF",
}

ENTITY_META = {
    "kospi": {"name": "KOSPI",      "is_index": True,  "fmt": ",.2f", "unit": ""},
    "sec":   {"name": "삼성전자",    "is_index": False, "fmt": ",.0f", "unit": "원"},
    "hynix": {"name": "SK하이닉스", "is_index": False, "fmt": ",.0f", "unit": "원"},
    "sem":   {"name": "삼성전기",    "is_index": False, "fmt": ",.0f", "unit": "원"},
}

ENTITY_COLORS = {k: C[k] for k in ("kospi", "sec", "hynix", "sem")}


# ── Plotly Figure → JSON dict (템플릿에서 JS로 직접 렌더링용) ────────────────
def _fig_to_spec(fig: go.Figure) -> dict:
    """Figure를 {data, layout} JSON-serializable dict로 변환."""
    raw = json.loads(pio.to_json(fig))
    return {"data": raw["data"], "layout": raw["layout"]}


def _uid() -> str:
    return "chart-" + str(uuid.uuid4())[:8]


# ── 공통 레이아웃 ─────────────────────────────────────────────────────────────
def _base_layout(title: str = "", height: int = 340) -> dict:
    return dict(
        title=dict(
            text=title,
            font=dict(family="-apple-system,'SF Pro Display',sans-serif",
                      size=13, color=C["font"]),
            x=0, xanchor="left", pad=dict(l=4),
        ),
        plot_bgcolor=C["bg"],
        paper_bgcolor=C["bg"],
        height=height,
        font=dict(family="-apple-system,'SF Pro Text',sans-serif",
                  size=11, color=C["font"]),
        margin=dict(l=12, r=64, t=44, b=32),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="white", bordercolor=C["grid"],
            font=dict(family="-apple-system,sans-serif", size=11),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="right", x=1,
            bgcolor="rgba(255,255,255,.85)",
            bordercolor=C["grid"], borderwidth=1,
            font=dict(size=10),
        ),
        xaxis=dict(
            showgrid=True, gridcolor=C["grid"], gridwidth=1,
            showline=False, zeroline=False,
            tickfont=dict(color=C["sub"], size=10),
        ),
        yaxis=dict(
            showgrid=True, gridcolor=C["grid"], gridwidth=1,
            showline=False, zeroline=False,
            tickfont=dict(color=C["sub"], size=10),
        ),
    )


# ── 이격도 배경 띠 + 임계선 ──────────────────────────────────────────────────
def _add_bands(fig: go.Figure) -> None:
    fig.add_hrect(y0=THRESHOLDS["overheat"], y1=175,
                  fillcolor="rgba(255,59,48,0.07)",  line_width=0, layer="below")
    fig.add_hrect(y0=THRESHOLDS["caution"],  y1=THRESHOLDS["overheat"],
                  fillcolor="rgba(255,149,0,0.07)", line_width=0, layer="below")
    fig.add_hrect(y0=THRESHOLDS["normal_upper"], y1=THRESHOLDS["caution"],
                  fillcolor="rgba(52,199,89,0.07)",  line_width=0, layer="below")
    fig.add_hrect(y0=60, y1=THRESHOLDS["normal_upper"],
                  fillcolor="rgba(0,122,255,0.07)",  line_width=0, layer="below")

    for y_val, color, label in [
        (THRESHOLDS["overheat"],     C["over"], "과열 130"),
        (THRESHOLDS["caution"],      C["caut"], "경계 120"),
        (THRESHOLDS["normal_upper"], C["norm"], "정상 105"),
        (100, C["grid"], "100"),
    ]:
        fig.add_hline(
            y=y_val,
            line_dash="dash" if y_val != 100 else "solid",
            line_color=color, line_width=1.1,
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(size=9, color=color),
        )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))


# ── 차트 빌더들 (모두 spec dict 반환) ────────────────────────────────────────

def build_price_chart(df: pd.DataFrame, key: str) -> dict:
    """주가 + 50일선 + 200일선."""
    meta  = ENTITY_META[key]
    color = ENTITY_COLORS[key]
    name  = meta["name"]
    unit  = meta["unit"]
    fmt   = ":" + meta["fmt"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index.astype(str).tolist(), y=df["ma200"].tolist(),
        name="200일선", mode="lines",
        line=dict(color=C["ma200"], width=1.4, dash="dot"),
        hovertemplate=f"%{{y{fmt}}}{unit}<extra>200일선</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index.astype(str).tolist(), y=df["ma50"].tolist(),
        name="50일선", mode="lines",
        line=dict(color=C["ma50"], width=1.4, dash="dash"),
        hovertemplate=f"%{{y{fmt}}}{unit}<extra>50일선</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index.astype(str).tolist(), y=df["close"].tolist(),
        name=name, mode="lines",
        line=dict(color=color, width=2),
        fill="tonexty",
        fillcolor=f"rgba({_hex_to_rgb(color)},0.06)",
        hovertemplate=f"%{{y{fmt}}}{unit}<extra>{name}</extra>",
    ))
    fig.update_layout(**_base_layout(f"{name} 주가 · 50일선 · 200일선"))
    return _fig_to_spec(fig)


def build_distance_chart(df: pd.DataFrame, key: str) -> dict:
    """50일 이격도 추이 + 배경 띠."""
    meta  = ENTITY_META[key]
    color = ENTITY_COLORS[key]
    name  = meta["name"]
    last  = df.iloc[-1]

    fig = go.Figure()
    _add_bands(fig)
    fig.add_trace(go.Scatter(
        x=df.index.astype(str).tolist(), y=df["distance50"].tolist(),
        name=f"{name} 50일 이격도", mode="lines",
        line=dict(color=color, width=2),
        hovertemplate="%{y:.2f}<extra>50일 이격도</extra>",
    ))
    # 현재값 마커
    fig.add_trace(go.Scatter(
        x=[str(last.name)], y=[last["distance50"]],
        mode="markers", showlegend=False,
        marker=dict(color=color, size=8, line=dict(color="white", width=2)),
        hoverinfo="skip",
    ))
    layout = _base_layout(f"{name} 50일 이격도 추이")
    d50_vals = df["distance50"].dropna()
    layout["yaxis"]["range"] = [
        min(60, float(d50_vals.min()) - 5),
        max(145, float(d50_vals.max()) + 5),
    ]
    fig.update_layout(**layout)
    return _fig_to_spec(fig)


def build_compare_distance_chart(all_data: dict) -> dict:
    """4종목 이격도 비교."""
    fig = go.Figure()
    _add_bands(fig)
    for key in ("kospi", "sec", "hynix", "sem"):
        df = all_data.get(key)
        if df is None or df.empty:
            continue
        meta  = ENTITY_META[key]
        color = ENTITY_COLORS[key]
        fig.add_trace(go.Scatter(
            x=df.index.astype(str).tolist(), y=df["distance50"].tolist(),
            name=meta["name"], mode="lines",
            line=dict(color=color, width=1.8),
            hovertemplate=f"%{{y:.2f}}<extra>{meta['name']}</extra>",
        ))
    layout = _base_layout("4종목 50일 이격도 비교", height=380)
    layout["yaxis"]["range"] = [60, 175]
    fig.update_layout(**layout)
    return _fig_to_spec(fig)


def build_compare_relative_chart(all_data: dict) -> dict:
    """기준점 100 상대 주가."""
    fig = go.Figure()
    fig.add_hline(y=100, line_dash="solid", line_color=C["grid"], line_width=1,
                  annotation_text="기준 100", annotation_position="right",
                  annotation_font=dict(size=9, color=C["sub"]))
    for key in ("kospi", "sec", "hynix", "sem"):
        df = all_data.get(key)
        if df is None or df.empty:
            continue
        meta  = ENTITY_META[key]
        color = ENTITY_COLORS[key]
        base  = df["close"].iloc[0]
        norm  = (df["close"] / base * 100).round(2)
        fig.add_trace(go.Scatter(
            x=df.index.astype(str).tolist(), y=norm.tolist(),
            name=meta["name"], mode="lines",
            line=dict(color=color, width=1.8),
            hovertemplate=f"%{{y:.1f}}<extra>{meta['name']}</extra>",
        ))
    layout = _base_layout("상대 주가 추이 (기준점 = 100)", height=340)
    fig.update_layout(**layout)
    return _fig_to_spec(fig)


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────

def render_dashboard(all_data: dict[str, pd.DataFrame],
                     output_path: str | None = None) -> str:
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "dashboard.html")

    # 요약 카드 & 테이블
    summaries: dict[str, dict] = {}
    tables:    dict[str, list] = {}
    for key, meta in ENTITY_META.items():
        df = all_data.get(key, pd.DataFrame())
        if df.empty:
            summaries[key] = {"name": meta["name"]}
            tables[key]    = []
            continue
        df = add_status_column(df)
        summaries[key] = get_latest_summary(df, name=meta["name"],
                                            is_index=meta["is_index"])
        tables[key]    = get_table_data(df, n=30, is_index=meta["is_index"])

    # 차트 스펙 (JSON dict) — 키: {price, distance}
    charts: dict[str, dict] = {}
    for key in ("kospi", "sec", "hynix", "sem"):
        df = all_data.get(key, pd.DataFrame())
        if df.empty:
            charts[key] = {"price": None, "distance": None}
        else:
            charts[key] = {
                "price":    build_price_chart(df, key),
                "distance": build_distance_chart(df, key),
            }

    chart_compare_distance = build_compare_distance_chart(all_data)
    chart_compare_relative = build_compare_relative_chart(all_data)

    # Jinja2 — autoescape=False: JSON을 script 태그 안에 안전하게 삽입
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)
    template = env.get_template("dashboard.html")

    html = template.render(
        summaries=summaries,
        tables=tables,
        charts=charts,
        chart_compare_distance=chart_compare_distance,
        chart_compare_relative=chart_compare_relative,
        charts_json=json.dumps({
            "kospi_price":    charts["kospi"]["price"],
            "kospi_distance": charts["kospi"]["distance"],
            "sec_price":      charts["sec"]["price"],
            "sec_distance":   charts["sec"]["distance"],
            "hynix_price":    charts["hynix"]["price"],
            "hynix_distance": charts["hynix"]["distance"],
            "sem_price":      charts["sem"]["price"],
            "sem_distance":   charts["sem"]["distance"],
            "compare_distance": chart_compare_distance,
            "compare_relative": chart_compare_relative,
        }, ensure_ascii=False),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        thresholds=THRESHOLDS,
        entity_meta=ENTITY_META,
        all_keys=["kospi", "sec", "hynix", "sem"],
        stock_keys=["sec", "hynix", "sem"],
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"대시보드 생성 완료: {output_path}")
    return output_path
