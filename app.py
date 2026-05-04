import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

# ── 폰트 및 리포트 테마 설정 ──────────────────────────────────
pio.templates["report"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
        margin=dict(t=40, b=40, l=40, r=40),
        hoverlabel=dict(bgcolor="white", font_size=13)
    )
)
pio.templates.default = "plotly_white+report"

st.set_page_config(page_title="야놀자 가격 전략 리포트", layout="wide")

# CSS: 전문 보고서 톤앤매너
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif !important; }
.overview-title { font-size: 22px; font-weight: 700; color: #1e293b; margin-bottom: 15px; }
.main-title { font-size: 24px; font-weight: 700; color: #0f172a; border-bottom: 3px solid #0f172a; padding-bottom: 10px; margin-bottom: 25px; margin-top: 10px;}
.section-header { font-size: 18px; font-weight: 700; color: #334155; margin-top: 30px; margin-bottom: 15px; padding-left: 8px; border-left: 4px solid #3b82f6; }
.briefing-box { background-color: #f1f5f9; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 25px; }
.criteria { font-size: 13px; color: #64748b; line-height: 1.5; margin-top: 10px;}
</style>
""", unsafe_allow_html=True)

# ── 데이터 처리 함수 ──────────────────────────────────────────
def read_data(file):
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=enc, skiprows=1 if "대실현황" in file.name else 0)
            df.columns = [c.lstrip('\ufeff').strip() for c in df.columns]
            return df
        except: continue
    return None

def to_num(x):
    if pd.isna(x): return 0
    s = str(x).replace(',', '').replace('원', '').strip()
    if s == '-' or s == '': return 0 
    try: return int(float(s))
    except: return 0

# ── 데이터 로드 ─────────────────────────────────────────────
import os

# ── 백단(서버) 데이터 자동 로드 ─────────────────────────────────────────────
# data 폴더 안의 파일 경로 지정
FILE_P = "data/price_data.csv"
FILE_M = "data/manager_map.csv"
FILE_C = "data/comp_match.csv"

# 세 파일이 모두 존재하는지 체크
if os.path.exists(FILE_P) and os.path.exists(FILE_M) and os.path.exists(FILE_C):
    # 파일을 읽기 모드(rb)로 열어서 기존 read_data 함수에 전달
    with open(FILE_P, 'rb') as f1, open(FILE_M, 'rb') as f2, open(FILE_C, 'rb') as f3:
        df_p = read_data(f1)
        df_m = read_data(f2)
        df_c = read_data(f3)


    # 전처리 및 병합
    df_p['지점코드_s'] = df_p['지점코드'].astype(str).str.split('.').str[0]
    df_p['대실_n'] = df_p['대실금액'].apply(to_num)
    df_p['숙박_n'] = df_p['숙박금액'].apply(to_num)

    df_m['지점코드_s'] = df_m['야놀자모텔'].astype(str).str.split('.').str[0]
    df_c['지점코드_s'] = df_c['지점코드'].astype(str).str.split('.').str[0]
    df_c['비교자사_s'] = df_c['비교대상자사코드'].astype(str).str.split('.').str[0]

    df_merged = pd.merge(df_p, df_c[['지점코드_s', '구분', '비교자사_s', '상권명']], on='지점코드_s', how='left')
    df_merged['구분'] = df_merged['구분'].fillna('자사')
    df_merged['매칭코드'] = df_merged.apply(lambda x: x['비교자사_s'] if x['구분'] == '경쟁사' else x['지점코드_s'], axis=1)
    
    df_final = pd.merge(df_merged, df_m[['지점코드_s', '현장담당자', '사업본부', '분류']], 
                        left_on='매칭코드', right_on='지점코드_s', how='left', suffixes=('', '_m'))

    # 자사 데이터 기준값 계산
    our_df_all = df_final[df_final['구분'] == '자사'].copy()
    med_d = our_df_all[our_df_all['대실_n'] > 0]['대실_n'].median()
    med_s = our_df_all[our_df_all['숙박_n'] > 0]['숙박_n'].median()

    # 요약 정보 계산
    total_rooms = len(our_df_all)
    closed_df = our_df_all[(our_df_all['대실_n'] == 0) & (our_df_all['숙박_n'] == 0)]
    closed_cnt = len(closed_df)
    issue_df = our_df_all[(our_df_all['대실_n'] > med_d * 2.0) | (our_df_all['숙박_n'] > med_s * 2.0)]
    issue_cnt = len(issue_df)

    # 상단 요약 (Overview)
    st.markdown("<div class='overview-title'>📊 통합 운영 개요 (Overview)</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 모니터링 객실", f"{total_rooms:,}개")
    c2.metric("마감/미판매 (전체 하이픈)", f"{closed_cnt:,}개", f"전체의 {closed_cnt/total_rooms*100:.1f}%")
    c3.metric("판매 중 객실", f"{total_rooms - closed_cnt:,}개")
    c4.metric("점검 필요 (이상 고단가)", f"{issue_cnt:,}개", delta="확인 요망", delta_color="inverse")
    
    st.divider()

    tab1, tab2, tab3 = st.tabs(["지점별 가격 현황", "전 지점 다각도 랭킹", "상권별 상세 비교"])

    # =========================================================================
    # TAB 1: 지점별 가격 현황
    # =========================================================================
    with tab1:
        st.markdown("<div class='main-title'>지점별 가격 노출 현황 및 점검 리포트</div>", unsafe_allow_html=True)
        
        # 특이 사항 점검
        st.markdown("<div class='section-header'>🚨 핵심 점검 사항 (이상 고단가)</div>", unsafe_allow_html=True)
        with st.container():
            st.markdown(f"""
            <div class='briefing-box'>
            현재 정상 판매 범위를 벗어난 '이상 고단가'로 의심되는 객실이 <b>총 {issue_cnt}건</b> 발견되었습니다.<br>
            <span style='color:#ef4444; font-weight:bold;'>(※ 대실/숙박 요금에 표시된 하이픈(-)은 '판매 마감' 또는 '미운영'으로 간주하여 점검 대상에서 정상 제외처리 되었습니다.)</span>
            <p class='criteria'>* 선정 기준: 대실 또는 숙박 요금이 전체 일반 단가(중앙값) 대비 2배 초과하여 등록된 객실</p>
            </div>
            """, unsafe_allow_html=True)
            
            issue_d = our_df_all[our_df_all['대실_n'] > med_d * 2.0][['현장담당자', '숙소명', '객실타입', '대실금액']]
            issue_d.columns = ['현장담당자', '지점명', '객실명', '금액']
            issue_s = our_df_all[our_df_all['숙박_n'] > med_s * 2.0][['현장담당자', '숙소명', '객실타입', '숙박금액']]
            issue_s.columns = ['현장담당자', '지점명', '객실명', '금액']

            col_i1, col_i2 = st.columns(2)
            with col_i1:
                st.markdown("**[대실] 이상 고단가 내역**")
                if not issue_d.empty:
                    st.dataframe(issue_d.reset_index(drop=True), use_container_width=True, height=200)
                else:
                    st.success("대실 고단가 특이 사항 없음")
            with col_i2:
                st.markdown("**[숙박] 이상 고단가 내역**")
                if not issue_s.empty:
                    st.dataframe(issue_s.reset_index(drop=True), use_container_width=True, height=200)
                else:
                    st.success("숙박 고단가 특이 사항 없음")

        # 분포도
        st.markdown("<div class='section-header'>전체 가격 분포도 (마감 객실 제외)</div>", unsafe_allow_html=True)
        target_mgr = st.multiselect("특정 담당자 지점만 보기 (미선택 시 전체)", sorted(our_df_all['현장담당자'].unique()))
        plot_df = our_df_all if not target_mgr else our_df_all[our_df_all['현장담당자'].isin(target_mgr)]

        for label, col, med_val in [("대실 가격 분포", "대실_n", med_d), ("숙박 가격 분포", "숙박_n", med_s)]:
            df_scat = plot_df[plot_df[col] > 0]
            fig = px.scatter(df_scat, x='숙소명', y=col, color='사업본부', hover_data=['객실타입', '대실금액' if col=='대실_n' else '숙박금액'], height=400)
            fig.add_hline(y=med_val, line_dash="dash", line_color="#f43f5e", annotation_text=f"중앙값 ({med_val:,.0f}원)", annotation_position="bottom right")
            fig.update_layout(title=label, xaxis_title=None, yaxis_title="요금(원)", xaxis_showticklabels=False)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # 지점별 심층 분석
        st.markdown("<div class='section-header'>지점별 상세 분석 (객실 단위)</div>", unsafe_allow_html=True)
        sel_hotel = st.selectbox("심층 분석할 지점을 선택하세요", sorted(our_df_all['숙소명'].unique()))
        
        if sel_hotel:
            target_df = our_df_all[our_df_all['숙소명'] == sel_hotel]
            
            st.markdown("**객실타입별 요금 비교 차트**")
            if not target_df.empty:
                melted = target_df.melt(id_vars=['객실타입'], value_vars=['대실_n', '숙박_n'], var_name='유형', value_name='가격')
                melted['유형'] = melted['유형'].replace({'대실_n': '대실', '숙박_n': '숙박'})
                
                fig_bar = px.bar(melted, y='객실타입', x='가격', color='유형', barmode='group', orientation='h',
                                 text_auto=',.0f', color_discrete_map={'대실': '#3b82f6', '숙박': '#10b981'}, height=450)
                fig_bar.update_layout(yaxis_title=None, xaxis_title="요금(원)")
                st.plotly_chart(fig_bar, use_container_width=True)

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.markdown("**[대실] 요금 상세**")
                st.dataframe(target_df[['객실타입', '대실상태', '대실금액']].reset_index(drop=True), use_container_width=True)
            with col_t2:
                st.markdown("**[숙박] 요금 상세**")
                st.dataframe(target_df[['객실타입', '숙박상태', '숙박금액']].reset_index(drop=True), use_container_width=True)

# =========================================================================
    # TAB 2: 전 지점 다각도 랭킹 분석 (전략 모니터링 보드)
    # =========================================================================
    with tab2:
        st.markdown("<div class='main-title'>전 지점 다각도 가격 전략 분석</div>", unsafe_allow_html=True)

        # 1. 가격 구분 선택 (상단 배치)
        mode = st.radio("분석 요금 구분", ["대실", "숙박"], horizontal=True)
        val_c = '대실_n' if mode == "대실" else '숙박_n'
        
        # 데이터 기초 필터링 (해당 요금제 판매 중인 객실만)
        active_rooms = our_df_all[our_df_all[val_c] > 0]

        # 🌟 2. 핵심 지표 4대 박스 (ADR 포함)
        if not active_rooms.empty:
            g_min = active_rooms[val_c].min()
            g_med = active_rooms[val_c].median()
            g_max = active_rooms[val_c].max()
            g_adr = active_rooms[val_c].mean() # ADR (Average Daily Rate)

            st.markdown("<div class='section-header'>전체 브랜드 가격 포지셔닝 요약</div>", unsafe_allow_html=True)
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            with kpi1:
                st.metric(label=f"브랜드 최저가 ({mode})", value=f"{g_min:,.0f}원")
                st.caption("고객 유입을 위한 최소 진입 가격")
            with kpi2:
                st.metric(label=f"브랜드 중앙값 ({mode})", value=f"{g_med:,.0f}원")
                st.caption("가장 보편적인 표준 판매 가격")
            with kpi3:
                st.metric(label=f"브랜드 최고가 ({mode})", value=f"{g_max:,.0f}원")
                st.caption("프리미엄/스위트룸 최대 단가")
            with kpi4:
                # 숙박일 경우 ADR로 표기, 대실일 경우 평균가로 표기
                label_name = "전체 ADR (평균객단가)" if mode == "숙박" else "전체 평균 대실가격"
                st.metric(label=label_name, value=f"{g_adr:,.0f}원", delta=f"중앙값 대비 {g_adr-g_med:+,.0f}", delta_color="normal")
                st.caption("수익성 판단의 기준 지표")
        
        st.divider()

       # 3. 상세 랭킹 분석
        st.markdown("<div class='section-header'>지점별 가격 서열 랭킹</div>", unsafe_allow_html=True)
        
        # 라디오 버튼 (상단 배치)
        agg_type = st.radio("순위 산정 기준 지표", ["최저가", "중앙값", "최고가"], horizontal=True)
        
        # 🌟 지능형 해석 문구 (버튼 하단에 작고 세련되게 배치)
        if agg_type == "최저가":
            st.markdown("<div style='font-size: 13px; color: #64748b; margin-top: -10px; margin-bottom: 20px;'>💡 <b>최저가 순위:</b> 상권 내에서 가장 공격적인 '미끼 상품(진입 단가)'을 운영 중인 지점을 확인합니다.</div>", unsafe_allow_html=True)
        elif agg_type == "중앙값":
            st.markdown("<div style='font-size: 13px; color: #64748b; margin-top: -10px; margin-bottom: 20px;'>💡 <b>중앙값 순위:</b> 지점별 '주력 상품'의 가격대를 비교하여 실질적인 단가(현실 단가) 수준을 파악합니다.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size: 13px; color: #64748b; margin-top: -10px; margin-bottom: 20px;'>💡 <b>최고가 순위:</b> 프리미엄 객실(파티룸, 스위트 등)의 가격을 비교하여 고단가 유도 현황을 파악합니다.</div>", unsafe_allow_html=True)

        # 랭킹 데이터 계산
        if agg_type == "최저가":
            rank_df = active_rooms.groupby('숙소명')[val_c].min().reset_index()
        elif agg_type == "중앙값":
            rank_df = active_rooms.groupby('숙소명')[val_c].median().reset_index()
        else:
            rank_df = active_rooms.groupby('숙소명')[val_c].max().reset_index()

        rank_df = rank_df.sort_values(val_c, ascending=True)
        
        # 그래프 생성 (가로 막대형)
        fig_r = px.bar(rank_df, 
                          y='숙소명', 
                          x=val_c, 
                          orientation='h',
                          text_auto=',.0f',
                          color=val_c,
                          color_continuous_scale='Blues',
                          height=max(600, len(rank_df)*25)) 
        
        # 기준선 추가 (선택한 지표의 전체 중앙값)
        ref_line = rank_df[val_c].median()
        fig_r.add_vline(x=ref_line, line_dash="dash", line_color="#ef4444", 
                        annotation_text=f"전체 기준선 ({ref_line:,.0f})", annotation_position="top right")
        
        fig_r.update_layout(yaxis_title=None, xaxis_title="금액(원)", coloraxis_showscale=False)
        st.plotly_chart(fig_r, use_container_width=True)

    # =========================================================================
    # TAB 3: 상권별 경쟁 분석 — 3층 구조 (스코어보드 → 드릴다운 → 액션)
    # =========================================================================
    with tab3:
        st.markdown("<div class='main-title'>상권별 경쟁 분석</div>", unsafe_allow_html=True)

        # ── 공통 설정 ─────────────────────────────────────────────────────
        mode_t3  = st.radio("분석 요금 기준", ["대실", "숙박"], horizontal=True, key="t3_mode")
        val_c3   = '대실_n' if mode_t3 == "대실" else '숙박_n'
        price_lbl = '대실금액' if mode_t3 == "대실" else '숙박금액'
        THRESHOLD_RED   = 0.10   # 경쟁사 대비 10% 초과 → 빨강 (경쟁사 우위)
        THRESHOLD_GREEN = -0.10  # 경쟁사 대비 10% 이하 → 초록 (자사 우위)

        # 유효 데이터(0원 제외)
        valid_df = df_final[df_final[val_c3] > 0].copy()
        # 상권 목록
        all_areas = sorted([a for a in df_final['상권명'].dropna().unique()])

        # ── 상권별 가격 격차 사전 계산 ────────────────────────────────────
        area_summary = []
        for area in all_areas:
            a_df = valid_df[valid_df['상권명'] == area]
            our_rows  = a_df[a_df['구분'] == '자사']
            comp_rows = a_df[a_df['구분'] == '경쟁사']
            if our_rows.empty or comp_rows.empty:
                continue
            our_min  = our_rows[val_c3].min()
            our_avg  = our_rows[val_c3].mean()
            comp_avg = comp_rows[val_c3].mean()
            gap_pct  = (our_avg - comp_avg) / comp_avg if comp_avg else 0

            if gap_pct > THRESHOLD_RED:
                status, color_cls = "경쟁사 우위", "🔴"
            elif gap_pct < THRESHOLD_GREEN:
                status, color_cls = "자사 우위", "🟢"
            else:
                status, color_cls = "비슷", "🟡"

            area_summary.append({
                "상권명": area,
                "status": status,
                "icon": color_cls,
                "gap_pct": gap_pct,
                "our_cnt": our_rows['숙소명'].nunique(),
                "comp_cnt": comp_rows['숙소명'].nunique(),
                "our_avg": our_avg,
                "comp_avg": comp_avg,
            })
        area_sum_df = pd.DataFrame(area_summary)

        # ══════════════════════════════════════════════════════════════════
        # LAYER 1 — 상권 경쟁력 스코어보드
        # ══════════════════════════════════════════════════════════════════
        st.markdown("<div class='section-header'>LAYER 1 — 전체 상권 경쟁력 스코어보드</div>",
                    unsafe_allow_html=True)
        st.markdown(
            "<div class='criteria'>"
            "🔴 경쟁사 우위: 자사 평균가가 경쟁사보다 10% 이상 높음 (가격 경쟁력 열세) &nbsp;|&nbsp; "
            "🟡 비슷: ±10% 이내 &nbsp;|&nbsp; "
            "🟢 자사 우위: 자사 평균가가 경쟁사보다 10% 이상 낮음"
            "</div>",
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)

        # 스코어보드 집계 요약 (최상단 3개 수치)
        if not area_sum_df.empty:
            n_red    = (area_sum_df['status'] == '경쟁사 우위').sum()
            n_yellow = (area_sum_df['status'] == '비슷').sum()
            n_green  = (area_sum_df['status'] == '자사 우위').sum()
            sb1, sb2, sb3 = st.columns(3)
            sb1.metric("🔴 즉시 조치 필요 상권", f"{n_red}개")
            sb2.metric("🟡 모니터링 상권",       f"{n_yellow}개")
            sb3.metric("🟢 가격 경쟁력 우위 상권", f"{n_green}개")
            st.markdown("<br>", unsafe_allow_html=True)

        # 상권 카드 그리드
        if area_sum_df.empty:
            st.warning("경쟁사 데이터가 있는 상권이 없습니다.")
        else:
            # 위험 순서로 정렬 (gap_pct 내림차순)
            area_sum_df_sorted = area_sum_df.sort_values('gap_pct', ascending=False)
            cols_per_row = 3
            rows = [area_sum_df_sorted.iloc[i:i+cols_per_row]
                    for i in range(0, len(area_sum_df_sorted), cols_per_row)]

            for row_data in rows:
                cols = st.columns(cols_per_row)
                for col, (_, row) in zip(cols, row_data.iterrows()):
                    gap_sign  = "+" if row['gap_pct'] >= 0 else ""
                    gap_str   = f"{gap_sign}{row['gap_pct']*100:.1f}%"

                    if row['status'] == '경쟁사 우위':
                        border_color = "#ef4444"
                        bg_color     = "#fff5f5"
                        gap_color    = "#c0392b"
                        status_html  = "<span style='background:#fde8e8;color:#c0392b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;'>경쟁사 우위</span>"
                    elif row['status'] == '자사 우위':
                        border_color = "#22c55e"
                        bg_color     = "#f0fdf4"
                        gap_color    = "#16a34a"
                        status_html  = "<span style='background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;'>자사 우위</span>"
                    else:
                        border_color = "#f59e0b"
                        bg_color     = "#fffbeb"
                        gap_color    = "#b45309"
                        status_html  = "<span style='background:#fef3c7;color:#b45309;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;'>비슷</span>"

                    with col:
                        st.markdown(f"""
                        <div style="background:{bg_color};border:1.5px solid {border_color};
                                    border-radius:10px;padding:14px 16px;margin-bottom:4px;">
                          <div style="font-size:14px;font-weight:700;color:#1e293b;
                                      margin-bottom:8px;">{row['상권명']}</div>
                          <div style="margin-bottom:6px;">{status_html}</div>
                          <div style="font-size:12px;color:#64748b;margin-bottom:2px;">
                            자사 {row['our_cnt']}개 &nbsp;·&nbsp; 경쟁사 {row['comp_cnt']}개
                          </div>
                          <div style="font-size:13px;font-weight:700;color:{gap_color};">
                            자사 평균가 {gap_str} 차이
                          </div>
                        </div>
                        """, unsafe_allow_html=True)

        st.divider()

        # ══════════════════════════════════════════════════════════════════
        # LAYER 2 — 선택 상권 드릴다운
        # ══════════════════════════════════════════════════════════════════
        st.markdown("<div class='section-header'>LAYER 2 — 상권 선택 후 상세 분석</div>",
                    unsafe_allow_html=True)

        sel_area = st.selectbox(
            "📍 분석할 상권을 선택하세요",
            options=all_areas,
            key="t3_area"
        )

        area_data = valid_df[valid_df['상권명'] == sel_area].copy()

        if area_data.empty:
            st.warning("해당 상권에 판매 중인 객실 데이터가 없습니다.")
        else:
            our_area  = area_data[area_data['구분'] == '자사']
            comp_area = area_data[area_data['구분'] == '경쟁사']

            # ── 2-A. 판정 요약 3박스 ───────────────────────────────────
            if not our_area.empty and not comp_area.empty:
                our_avg_d  = our_area['대실_n'][our_area['대실_n'] > 0].mean()
                comp_avg_d = comp_area['대실_n'][comp_area['대실_n'] > 0].mean()
                our_avg_s  = our_area['숙박_n'][our_area['숙박_n'] > 0].mean()
                comp_avg_s = comp_area['숙박_n'][comp_area['숙박_n'] > 0].mean()

                def gap_text(our, comp):
                    if our == 0 or comp == 0 or (pd.isna(our)) or (pd.isna(comp)):
                        return "데이터 없음", "#888", "-"
                    g = (our - comp) / comp
                    sign = "+" if g >= 0 else ""
                    txt  = f"{sign}{g*100:.1f}%"
                    if g > THRESHOLD_RED:
                        return txt, "#c0392b", "자사 고단가 ↑"
                    elif g < THRESHOLD_GREEN:
                        return txt, "#16a34a", "자사 저단가 ↓"
                    else:
                        return txt, "#b45309", "비슷한 수준"

                d_txt, d_col, d_sub = gap_text(our_avg_d, comp_avg_d)
                s_txt, s_col, s_sub = gap_text(our_avg_s, comp_avg_s)

                verdict = "조치 필요 🚨" if d_col == "#c0392b" or s_col == "#c0392b" else \
                          "양호 ✅"      if d_col == "#16a34a" and s_col == "#16a34a" else \
                          "모니터링 👀"

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.markdown(f"""
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
                                padding:16px;text-align:center;">
                      <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">대실 가격 격차</div>
                      <div style="font-size:26px;font-weight:700;color:{d_col};">{d_txt}</div>
                      <div style="font-size:11px;color:{d_col};margin-top:2px;">{d_sub}</div>
                    </div>""", unsafe_allow_html=True)
                with mc2:
                    st.markdown(f"""
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
                                padding:16px;text-align:center;">
                      <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">숙박 가격 격차</div>
                      <div style="font-size:26px;font-weight:700;color:{s_col};">{s_txt}</div>
                      <div style="font-size:11px;color:{s_col};margin-top:2px;">{s_sub}</div>
                    </div>""", unsafe_allow_html=True)
                with mc3:
                    v_color = "#c0392b" if "조치" in verdict else "#16a34a" if "양호" in verdict else "#b45309"
                    st.markdown(f"""
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
                                padding:16px;text-align:center;">
                      <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">종합 판정</div>
                      <div style="font-size:18px;font-weight:700;color:{v_color};margin-top:6px;">{verdict}</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

            # ── 2-B. 지점별 최저가 비교 가로 바 차트 ─────────────────
            st.markdown("<div class='section-header' style='font-size:15px;'>지점별 최저가 비교</div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<div class='criteria'>자사(빨강)와 경쟁사(파랑)의 {mode_t3} 최저가를 나란히 비교합니다.</div>",
                unsafe_allow_html=True
            )

            # 지점별 최저가 집계
            bar_df = area_data.groupby(['숙소명', '구분'])[val_c3].min().reset_index()
            bar_df.columns = ['숙소명', '구분', '최저가']
            bar_df = bar_df.sort_values('최저가', ascending=True)

            fig_bar = px.bar(
                bar_df, y='숙소명', x='최저가',
                color='구분',
                orientation='h',
                text_auto=',.0f',
                color_discrete_map={'자사': '#ef4444', '경쟁사': '#3b82f6'},
                height=max(300, len(bar_df) * 36),
                labels={'최저가': f'{mode_t3} 최저가 (원)', '숙소명': ''},
            )
            # 경쟁사 평균선 추가
            if not comp_area.empty:
                comp_min_avg = comp_area.groupby('숙소명')[val_c3].min().mean()
                fig_bar.add_vline(
                    x=comp_min_avg, line_dash="dash", line_color="#3b82f6",
                    annotation_text=f"경쟁사 평균 ({comp_min_avg:,.0f}원)",
                    annotation_position="top right",
                )
            fig_bar.update_layout(
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                yaxis_title=None, xaxis_tickformat=',',
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            st.divider()

            # ── 2-C. 1:1 헤드투헤드 비교 ──────────────────────────────
            st.markdown("<div class='section-header' style='font-size:15px;'>1:1 라이벌 헤드투헤드</div>",
                        unsafe_allow_html=True)

            our_hotels  = sorted(our_area['숙소명'].unique())
            comp_hotels = sorted(comp_area['숙소명'].unique())

            if our_hotels and comp_hotels:
                hh1, hh2 = st.columns(2)
                with hh1:
                    sel_our  = st.selectbox("🔴 자사 지점 선택", our_hotels, key="t3_our")
                with hh2:
                    sel_comp = st.selectbox("🔵 경쟁사 지점 선택", comp_hotels, key="t3_comp")

                vs_df = area_data[area_data['숙소명'].isin([sel_our, sel_comp])].copy()

                fig_vs = px.bar(
                    vs_df, x='객실타입', y=val_c3,
                    color='숙소명', barmode='group',
                    text_auto=',.0f',
                    color_discrete_map={sel_our: '#ef4444', sel_comp: '#3b82f6'},
                    labels={val_c3: f'{mode_t3} 요금 (원)', '객실타입': ''},
                    height=400,
                )
                fig_vs.update_layout(
                    xaxis_tickangle=-30,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02),
                )
                st.plotly_chart(fig_vs, use_container_width=True)

                # 헤드투헤드 수치 비교 테이블
                our_stats  = vs_df[vs_df['숙소명'] == sel_our][val_c3]
                comp_stats = vs_df[vs_df['숙소명'] == sel_comp][val_c3]
                hh_cols = st.columns(4)
                for metric, our_val, comp_val in [
                    ("최저가", our_stats.min(), comp_stats.min()),
                    ("평균가", our_stats.mean(), comp_stats.mean()),
                    ("중앙값", our_stats.median(), comp_stats.median()),
                    ("최고가", our_stats.max(), comp_stats.max()),
                ]:
                    if our_val > 0 and comp_val > 0:
                        diff = (our_val - comp_val) / comp_val * 100
                        arrow = "↑" if diff > 0 else "↓"
                        diff_color = "#c0392b" if diff > 0 else "#16a34a"
                        with hh_cols[["최저가","평균가","중앙값","최고가"].index(metric)]:
                            st.markdown(f"""
                            <div style="background:#f8fafc;border:1px solid #e2e8f0;
                                        border-radius:8px;padding:12px;text-align:center;">
                              <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">{metric}</div>
                              <div style="font-size:13px;color:#ef4444;font-weight:600;">
                                자사 {our_val:,.0f}원</div>
                              <div style="font-size:13px;color:#3b82f6;">
                                경쟁 {comp_val:,.0f}원</div>
                              <div style="font-size:12px;font-weight:700;color:{diff_color};margin-top:4px;">
                                {arrow} {abs(diff):.1f}%</div>
                            </div>""", unsafe_allow_html=True)
            else:
                st.info("이 상권에는 자사와 경쟁사가 함께 존재하지 않아 1:1 비교가 불가합니다.")

            st.divider()

            # ── 2-D. 상권 내 전체 요금표 ──────────────────────────────
            st.markdown("<div class='section-header' style='font-size:15px;'>상권 내 전체 객실 요금표</div>",
                        unsafe_allow_html=True)
            disp_cols = ['구분', '숙소명', '객실타입', '대실금액', '숙박금액']
            disp_df   = df_final[df_final['상권명'] == sel_area][disp_cols].sort_values(['구분', '숙소명'])
            st.dataframe(disp_df.reset_index(drop=True), use_container_width=True, height=300)

        st.divider()

       # ══════════════════════════════════════════════════════════════════
        # LAYER 3 — 즉시 조치 필요 지점 액션 포인트 (고도화 버전)
        # ══════════════════════════════════════════════════════════════════
        st.markdown("<div class='section-header'>🚨 LAYER 3 — 즉시 조치 필요 지점 (전체 상권 통합)</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='criteria'>"
            "경쟁사 상권 평균 대비 <b>자사 요금이 10% 이상 높은 지점(위험)</b> 또는 <b>10% 이상 저렴한 지점(기회 손실)</b>을 자동 추출합니다.<br>"
            "담당자는 하단 리스트를 다운로드하여 즉각적인 단가 재검토를 진행해 주시기 바랍니다."
            "</div>",
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)

        THRESHOLD_RED = 0.10  # 10% 이상 비쌀 때 (조치 필요)
        THRESHOLD_BLUE = -0.10 # 10% 이상 쌀 때 (단가 인상 기회)

        action_rows = []
        
        # valid_df, all_areas, val_c3, mode_t3 등은 기존 변수 그대로 사용
        for area in all_areas:
            a_df = valid_df[valid_df['상권명'] == area]
            our_rows  = a_df[a_df['구분'] == '자사']
            comp_rows = a_df[a_df['구분'] == '경쟁사']
            
            if our_rows.empty or comp_rows.empty:
                continue

            # 경쟁사 지표 계산 (평균 및 최저가)
            comp_avg_area = comp_rows[val_c3].mean()
            comp_min_area = comp_rows[val_c3].min()

            for hotel in our_rows['숙소명'].unique():
                h_df     = our_rows[our_rows['숙소명'] == hotel]
                our_avg  = h_df[val_c3].mean()
                our_min  = h_df[val_c3].min() # 진입 단가 비교용
                
                if comp_avg_area == 0:
                    continue
                    
                gap = (our_avg - comp_avg_area) / comp_avg_area
                
                # 10% 이상 비싸거나(경고), 10% 이상 싸거나(기회)
                if gap > THRESHOLD_RED or gap < THRESHOLD_BLUE:
                    mgr = h_df['현장담당자'].dropna().iloc[0] if '현장담당자' in h_df.columns and not h_df['현장담당자'].dropna().empty else '미배정'
                    
                    # 상태 판별
                    status = "🔴 단가 인하 검토" if gap > 0 else "🔵 단가 인상 기회"
                    
                    action_rows.append({
                        "상권명":      area,
                        "지점명":      hotel,
                        "담당자":      mgr,
                        "조치 권고":    status,
                        f"자사 {mode_t3} 평균가": int(our_avg),
                        "경쟁사 평균가":  int(comp_avg_area),
                        "격차 (%)":    f"{gap*100:+.1f}%",
                        "자사 최저가": int(our_min),
                        "경쟁사 최저가": int(comp_min_area),
                        "_gap_abs":    abs(gap), # 정렬용 절대값
                    })

        if action_rows:
            action_df = pd.DataFrame(action_rows).sort_values('_gap_abs', ascending=False).drop(columns=['_gap_abs'])
            
            # 위험/기회 건수 카운트
            red_cnt = len(action_df[action_df['조치 권고'].str.contains("인하")])
            blue_cnt = len(action_df[action_df['조치 권고'].str.contains("인상")])
            
            st.markdown(
                f"<div style='font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 15px;'>"
                f"총 {red_cnt}개 지점이 고단가 경고, {blue_cnt}개 지점이 단가 인상 기회로 포착되었습니다."
                f"</div>", 
                unsafe_allow_html=True)
            
            # 판다스 스타일링으로 가독성 극대화
            def style_action(row):
                if "🔴" in row['조치 권고']:
                    return ['background-color: #fee2e2; color: #991b1b'] * len(row)
                elif "🔵" in row['조치 권고']:
                    return ['background-color: #e0f2fe; color: #075985'] * len(row)
                return [''] * len(row)

            st.dataframe(action_df.style.apply(style_action, axis=1), use_container_width=True, height=350)

            csv_bytes = action_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                "⬇️ 조치 필요 지점 통합 리포트 CSV 다운로드",
                csv_bytes,
                file_name="프라이싱_조치필요리포트.csv",
                mime="text/csv",
            )
        else:
            st.success(f"현재 {mode_t3} 기준, 상권 대비 10% 이상 차이나는 특이 지점이 없습니다.")

else:
    st.error("🚨 데이터 연동 에러: 서버의 'data' 폴더에 필수 CSV 파일 3개가 모두 있는지 확인해 주세요.")