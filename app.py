import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

# ── 폰트 및 스타일 설정 ──────────────────────────────────────────
pio.templates["kor"] = go.layout.Template(
    layout=go.Layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif"))
)
pio.templates.default = "plotly+kor"

st.set_page_config(page_title="야놀자 통합 운영/경쟁 대시보드", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif !important; }
.stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #e9ecef; }
</style>
""", unsafe_allow_html=True)

st.title("🏨 야놀자 통합 운영 및 경쟁사 모니터링 대시보드")


# ── 유틸리티 함수 ────────────────────────────────────────────────

def read_korean_csv(file, skip_rows=0):
    """여러 인코딩을 순차 시도해 CSV를 읽는다."""
    encodings = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]
    last_err = None
    for enc in encodings:
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=enc, skiprows=skip_rows)
            df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
            df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
            return df
        except Exception as e:
            last_err = e
    # 최후 수단
    file.seek(0)
    df = pd.read_csv(file, encoding="utf-8", errors="ignore", skiprows=skip_rows)
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    st.warning(f"파일 인코딩 감지 실패 — utf-8(ignore) 로 읽었습니다. ({last_err})")
    return df


def to_id(val):
    if pd.isna(val):
        return "0"
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


def clean_price(x):
    if pd.isna(x):
        return 0
    s = str(x).strip().replace(",","").replace("원","").replace('"',"").replace("'","")
    if s in ("-", "", "정보없음", "nan", "None"):
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def safe_mean(series):
    """0 제외 평균, 값 없으면 None."""
    filtered = series[series > 0]
    return filtered.mean() if len(filtered) > 0 else None


def require_cols(df, cols, label):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"[{label}] 필수 컬럼 누락: {missing}\n실제 컬럼: {df.columns.tolist()}")
        return False
    return True


# ── 1. 파일 업로드 (사이드바) ────────────────────────────────────
st.sidebar.header("📂 데이터 업로드")
f_price    = st.sidebar.file_uploader("1️⃣ 가격 데이터 (자사/경쟁사 수집본)", type=["csv"])
f_manager  = st.sidebar.file_uploader("2️⃣ 담당자 맵핑 (자사 관리용)",       type=["csv"])
f_comp_map = st.sidebar.file_uploader("3️⃣ 경쟁사 매칭 (상권 분석용)",       type=["csv"])

if not (f_price and f_manager and f_comp_map):
    st.info("💡 왼쪽 사이드바에서 CSV 파일 3개를 모두 업로드해 주세요.")
    st.stop()


# ── 2. 로드 & 필수 컬럼 검증 ────────────────────────────────────
df_p = read_korean_csv(f_price, skip_rows=0)
if "지점코드" not in df_p.columns:
    df_p = read_korean_csv(f_price, skip_rows=1)

df_m = read_korean_csv(f_manager, skip_rows=0)
df_c = read_korean_csv(f_comp_map, skip_rows=0)

if not require_cols(df_p, ["지점코드"], "가격 데이터"): st.stop()
if not require_cols(df_m, ["야놀자모텔","현장담당자","사업본부","분류"], "담당자 맵핑"): st.stop()
if not require_cols(df_c, ["지점코드","구분","비교대상자사코드","상권명"], "경쟁사 매칭"): st.stop()


# ── 3. 전처리 ────────────────────────────────────────────────────
df_p = df_p.copy()
df_p["지점코드_str"] = df_p["지점코드"].apply(to_id)
df_p["대실_n"] = df_p["대실금액"].apply(clean_price) if "대실금액" in df_p.columns else 0
df_p["숙박_n"] = df_p["숙박금액"].apply(clean_price) if "숙박금액" in df_p.columns else 0

df_m = df_m.copy()
df_m["야놀자모텔_str"] = df_m["야놀자모텔"].apply(to_id)

# ✅ 중복 지점코드로 인한 행 폭증 방지
df_c = df_c.copy()
df_c["지점코드_str"] = df_c["지점코드"].apply(to_id)
df_c["비교자사_str"] = df_c["비교대상자사코드"].apply(to_id)
df_c_dedup = (
    df_c[["지점코드_str","구분","비교자사_str","상권명"]]
    .drop_duplicates(subset="지점코드_str")
)

df_merged = pd.merge(df_p, df_c_dedup, on="지점코드_str", how="left")
df_merged.loc[df_merged["구분"]=="자사", "비교자사_str"] = df_merged["지점코드_str"]

df_final = pd.merge(
    df_merged,
    df_m[["야놀자모텔_str","현장담당자","사업본부","분류"]],
    left_on="비교자사_str", right_on="야놀자모텔_str", how="left"
)

df_final["구분"]       = df_final["구분"].fillna("자사")
df_final["현장담당자"] = df_final["현장담당자"].fillna("미지정")
df_final["사업본부"]   = df_final["사업본부"].fillna("미분류")
df_final["분류"]       = df_final["분류"].fillna("미분류")
df_final["상권명"]     = df_final["상권명"].fillna("상권미지정")

# ✅ 상태 컬럼 없을 경우 기본값으로 생성
for col in ["대실상태", "숙박상태"]:
    if col not in df_final.columns:
        df_final[col] = "정보없음"
        st.warning(f"'{col}' 컬럼이 없어 '정보없음' 으로 채웠습니다.")


# ── 4. 사이드바 필터 ─────────────────────────────────────────────
st.sidebar.header("🔎 통합 필터")

sel_dept = st.sidebar.selectbox(
    "🏢 사업본부", ["전체"] + sorted(df_final["사업본부"].dropna().unique().tolist()))
base_m = df_final if sel_dept == "전체" else df_final[df_final["사업본부"] == sel_dept]

sel_mgr = st.sidebar.selectbox(
    "👤 현장담당자", ["전체"] + sorted(base_m["현장담당자"].dropna().unique().tolist()))
base_t = base_m if sel_mgr == "전체" else base_m[base_m["현장담당자"] == sel_mgr]

type_options = sorted(base_t["분류"].dropna().unique().tolist())
sel_type = st.sidebar.multiselect("🏗️ 운영방식", ["전체"]+type_options, default=["전체"])

area_options = sorted(base_t["상권명"].dropna().unique().tolist())
sel_area = st.sidebar.multiselect("📍 상권선택", ["전체"]+area_options, default=["전체"])

type_filter = type_options if "전체" in sel_type else sel_type
area_filter = area_options if "전체" in sel_area else sel_area

dff = base_t[(base_t["분류"].isin(type_filter)) & (base_t["상권명"].isin(area_filter))]

if dff.empty:
    st.warning("⚠️ 선택한 필터 조건에 해당하는 데이터가 없습니다. 필터를 조정해 주세요.")
    st.stop()


# ── 5. KPI ───────────────────────────────────────────────────────
st.markdown("### 📊 통합 핵심 지표")
k1, k2, k3, k4, k5, k6 = st.columns(6)

our  = dff[dff["구분"] == "자사"]
comp = dff[dff["구분"] == "경쟁사"]

our_d  = safe_mean(our["대실_n"])
comp_d = safe_mean(comp["대실_n"])
our_s  = safe_mean(our["숙박_n"])
comp_s = safe_mean(comp["숙박_n"])

gap_d = (our_d - comp_d) if (our_d is not None and comp_d is not None) else None
gap_s = (our_s - comp_s) if (our_s is not None and comp_s is not None) else None

fmt     = lambda v: f"{v:,.0f}원" if v is not None else "-"
fmt_gap = lambda v: f"{v:+,.0f}원" if v is not None else "-"

k1.metric("자사 모니터링 지점", f"{our['숙소명'].nunique()}개")
k2.metric("가능 객실 (대실/숙박)",
    f"{len(our[our['대실상태']=='가능'])} / {len(our[our['숙박상태']=='가능'])}")
k3.metric("자사 대실 평균가", fmt(our_d))
k4.metric("대실 Gap (자사-경쟁)", fmt_gap(gap_d),
    delta=fmt_gap(gap_d) if gap_d is not None else None,
    delta_color="normal" if (gap_d is None or gap_d <= 0) else "inverse")
k5.metric("자사 숙박 평균가", fmt(our_s))
k6.metric("숙박 Gap (자사-경쟁)", fmt_gap(gap_s),
    delta=fmt_gap(gap_s) if gap_s is not None else None,
    delta_color="normal" if (gap_s is None or gap_s <= 0) else "inverse")

st.divider()


# ── 6. 탭 ────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🏢 내부 운영 관리", "⚔️ 대외 경쟁 분석", "📋 상세 데이터"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 운영방식 및 본부별 지점 비중")
        sun_df = our[our["대실_n"] > 0]
        if sun_df.empty:
            st.info("표시할 대실 데이터가 없습니다.")
        else:
            fig_p = px.sunburst(sun_df, path=["사업본부","분류"], values="대실_n",
                color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
    with c2:
        st.markdown("#### 담당자별 관리 지점 현황")
        mc = (our[["현장담당자","숙소명"]].drop_duplicates()
              ["현장담당자"].value_counts().reset_index())
        mc.columns = ["담당자","지점수"]
        if mc.empty:
            st.info("담당자 데이터가 없습니다.")
        else:
            fig_b = px.bar(mc, x="담당자", y="지점수", text="지점수", color="담당자")
            fig_b.update_layout(showlegend=False)
            st.plotly_chart(fig_b, use_container_width=True)

with tab2:
    view_type = st.radio("💰 비교 기준 요금", ["대실 요금 기준","숙박 요금 기준"], horizontal=True)
    col_y = "대실_n" if view_type == "대실 요금 기준" else "숙박_n"
    color_map = ({"자사":"#10b981","경쟁사":"#94a3b8"} if view_type == "숙박 요금 기준"
                 else {"자사":"#3b82f6","경쟁사":"#94a3b8"})

    area_avg = (dff[dff[col_y] > 0]
                .groupby(["상권명","구분"])[[col_y]].mean().reset_index())

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown(f"#### 🏘️ 상권별 평균 가격 비교 ({view_type})")
        if area_avg.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            fig_area = px.bar(area_avg, x="상권명", y=col_y, color="구분",
                barmode="group", text_auto=",.0f", color_discrete_map=color_map)
            st.plotly_chart(fig_area, use_container_width=True)

    with cc2:
        st.markdown(f"#### 💰 자사-경쟁사 가격 Gap 추이 ({view_type})")
        if area_avg.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            # ✅ pivot → pivot_table 으로 중복 인덱스 안전 처리
            area_pivot = area_avg.pivot_table(
                index="상권명", columns="구분", values=col_y, aggfunc="mean"
            ).reset_index()
            if "자사" in area_pivot.columns and "경쟁사" in area_pivot.columns:
                area_pivot["Gap"] = area_pivot["자사"] - area_pivot["경쟁사"]
                # ✅ 외부 Series 전달 버그 수정 → 컬럼으로 참조
                area_pivot["Gap_label"] = area_pivot["Gap"].apply(
                    lambda x: f"{x:,.0f}" if pd.notna(x) else "")
                fig_gap = px.line(area_pivot, x="상권명", y="Gap",
                    markers=True, text="Gap_label")
                fig_gap.update_traces(textposition="top center")
                fig_gap.add_hline(y=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig_gap, use_container_width=True)
            else:
                missing_g = [g for g in ["자사","경쟁사"] if g not in area_pivot.columns]
                st.info(f"Gap 계산을 위한 구분값 부족: {missing_g}")

with tab3:
    st.markdown("#### 📋 통합 상세 리스트")
    # ✅ 실제 존재하는 컬럼만 선택 (KeyError 방지)
    want_cols = ["상권명","사업본부","분류","현장담당자","구분","숙소명",
                 "객실타입","대실상태","대실금액","숙박상태","숙박금액","수집일시"]
    disp_cols    = [c for c in want_cols if c in dff.columns]
    missing_cols = [c for c in want_cols if c not in dff.columns]
    if missing_cols:
        st.caption(f"ℹ️ 다음 컬럼은 데이터에 없어 생략되었습니다: {missing_cols}")

    sort_by = [c for c in ["상권명","구분"] if c in disp_cols]
    st.dataframe(dff[disp_cols].sort_values(sort_by).reset_index(drop=True),
        use_container_width=True)

    csv = dff[disp_cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇️ 분석 데이터 다운로드", csv, "야놀자_통합분석.csv", "text/csv")