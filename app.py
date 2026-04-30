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
with st.sidebar:
    st.header("데이터 업로드")
    f1 = st.file_uploader("1. 가격 데이터 (통합)", type=['csv'])
    f2 = st.file_uploader("2. 담당자 맵핑", type=['csv'])
    f3 = st.file_uploader("3. 경쟁사 매칭", type=['csv'])

if f1 and f2 and f3:
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
    # TAB 2: 전 지점 다각도 랭킹 분석 (🌟 빨간 기준선 복구 완료!)
    # =========================================================================
    with tab2:
        st.markdown("<div class='main-title'>전 지점 다각도 랭킹 분석</div>", unsafe_allow_html=True)
        mode = st.radio("분석 요금", ["대실", "숙박"], horizontal=True)
        agg_type = st.radio("지표", ["최저가 (시작단가)", "중앙값 (일반단가)", "최고가 (프리미엄단가)"], horizontal=True)
        val_c = '대실_n' if mode == "대실" else '숙박_n'
        
        base_df = our_df_all[our_df_all[val_c] > 0] # 마감/0원 제외
        
        if "최저가" in agg_type: rank_df = base_df.groupby('숙소명')[val_c].min().reset_index()
        elif "중앙값" in agg_type: rank_df = base_df.groupby('숙소명')[val_c].median().reset_index()
        else: rank_df = base_df.groupby('숙소명')[val_c].max().reset_index()
        
        rank_df = rank_df.sort_values(val_c, ascending=True)
        
        # 🌟 누락되었던 지점별 중앙값(빨간선) 다시 계산 및 추가
        global_ref = rank_df[val_c].median() 

        fig_r = px.bar(rank_df, y='숙소명', x=val_c, orientation='h', text_auto=',.0f', color=val_c, color_continuous_scale='Blues', height=max(600, len(rank_df)*25))
        
        # 🌟 여기에 다시 빨간 점선을 꽂아 넣었습니다!
        fig_r.add_vline(x=global_ref, line_dash="dash", line_color="#ef4444", annotation_text="지점 중앙값", annotation_position="top right")
        
        fig_r.update_layout(yaxis_title=None, xaxis_title="요금(원)", coloraxis_showscale=False)
        st.plotly_chart(fig_r, use_container_width=True)

    # =========================================================================
    # TAB 3: 상권별 상세 비교
    # =========================================================================
    with tab3:
        st.markdown("<div class='main-title'>상권 내 라이벌 매칭 상세 분석</div>", unsafe_allow_html=True)
        sel_area = st.selectbox("상권 선택", sorted([a for a in df_final['상권명'].unique() if pd.notna(a)]))
        area_data = df_final[df_final['상권명'] == sel_area].copy()
        st.dataframe(area_data[['구분', '숙소명', '객실타입', '대실금액', '숙박금액']].sort_values(['구분', '대실금액'], ascending=[False, False]), use_container_width=True)

else:
    st.info("좌측 사이드바에 파일을 업로드해 주세요.")