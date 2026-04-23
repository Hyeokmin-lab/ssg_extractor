"""
SSG.COM 상품 정보 추출기 - Streamlit UI
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import time
import requests

from ssg_product_extractor import create_driver, extract_product

st.set_page_config(
    page_title="SSG.COM 상품 정보 추출기",
    page_icon="🛒",
    layout="centered",
)

st.markdown("""
<style>
    .main .block-container { max-width: 720px; padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-size: 1.8rem !important; font-weight: 700 !important; }
    textarea { font-size: 0.875rem !important; background-color: #f8f9fa !important; border-radius: 6px !important; }
    .stButton > button { height: 48px; font-size: 0.95rem; font-weight: 600; border-radius: 6px; }
    .stButton > button[kind="primary"] { background-color: #e74c3c !important; border-color: #e74c3c !important; }
    .stButton > button[kind="primary"]:hover { background-color: #c0392b !important; border-color: #c0392b !important; }
    .status-box { background: #f0f4ff; border-left: 4px solid #3b82f6; padding: 10px 14px; border-radius: 4px; font-size: 0.875rem; color: #1e40af; margin: 8px 0; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    hr { margin: 1.2rem 0 !important; }
    .stDownloadButton > button { background-color: #22c55e !important; color: white !important; border-color: #22c55e !important; height: 44px; font-weight: 600; border-radius: 6px; width: 100%; }
    .product-header { background: #f8f9fa; border-left: 4px solid #e74c3c; padding: 10px 14px; border-radius: 4px; margin: 20px 0 10px 0; }
    .product-meta { color: #666; font-size: 0.85rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# 세션 상태
if "results" not in st.session_state:
    st.session_state.results = []
if "log_msgs" not in st.session_state:
    st.session_state.log_msgs = []

st.title("🛒 SSG.COM 상품 정보 추출기")
st.markdown("---")

# URL 입력
st.markdown("🔗 **SSG.COM 상품 URL 입력**")
urls_input = st.text_area(
    label="urls",
    label_visibility="collapsed",
    placeholder="URL을 한 줄에 하나씩 입력하세요.\n(예: https://www.ssg.com/item/itemView.ssg?itemId=1000795246042)",
    height=160,
    key="url_textarea",
)

st.markdown("---")

# 버튼 행
col_start, col_reset = st.columns([2, 1])
with col_start:
    start_btn = st.button("🔍 추출 시작", use_container_width=True, type="primary")
with col_reset:
    reset_btn = st.button("🔄 초기화", use_container_width=True)

if reset_btn:
    st.session_state.results = []
    st.session_state.log_msgs = []
    st.rerun()

# 추출 실행
if start_btn:
    raw_urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
    if not raw_urls:
        st.warning("URL을 한 줄 이상 입력해주세요.")
    else:
        st.session_state.results = []
        st.session_state.log_msgs = []

        prog_bar   = st.progress(0)
        status_box = st.empty()
        log_area   = st.empty()
        results    = []
        log_msgs   = []

        def update_log(msg):
            log_msgs.append(msg)
            log_area.markdown("\n".join(f"- {m}" for m in log_msgs[-5:]), unsafe_allow_html=True)

        driver = create_driver(headless=True)
        try:
            for idx, url in enumerate(raw_urls):
                status_box.markdown(
                    f'<div class="status-box">⏳ 처리 중... ({idx+1} / {len(raw_urls)})  <code>{url[:70]}</code></div>',
                    unsafe_allow_html=True,
                )
                update_log(f"[{idx+1}] {url[:60]}... 추출 시작")
                res = extract_product(driver, url, status_callback=update_log)
                results.append(res)
                if res["오류"]:
                    update_log(f"  ❌ 오류: {res['오류'][:60]}")
                else:
                    update_log(f"  ✅ 완료 | {res['브랜드']} | {res['상품명'][:30]}")
                prog_bar.progress((idx + 1) / len(raw_urls))
                time.sleep(0.5)
        finally:
            driver.quit()

        st.session_state.results  = results
        st.session_state.log_msgs = log_msgs
        status_box.markdown(
            f'<div class="status-box" style="border-color:#22c55e;background:#f0fdf4;color:#15803d;">'
            f"✅ 완료! 총 {len(results)}개 상품 추출 완료</div>",
            unsafe_allow_html=True,
        )

# 결과 표시
if st.session_state.results:
    st.markdown("---")
    st.subheader(f"📋 추출 결과 ({len(st.session_state.results)}개)")

    df = pd.DataFrame(st.session_state.results)
    display_cols = ["브랜드", "상품명", "판매가", "색상", "사이즈", "모델번호", "오류"]
    st.dataframe(df[[c for c in display_cols if c in df.columns]], use_container_width=True, height=300)

    # Excel 생성
    def build_excel(results):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SSG 상품정보"
        headers    = ["번호", "브랜드", "상품명", "판매가", "색상", "사이즈", "모델번호", "URL", "상품상세이미지URL", "오류"]
        col_widths = [6, 16, 50, 12, 30, 30, 16, 50, 60, 30]
        header_fill  = PatternFill("solid", fgColor="C0392B")
        header_font  = Font(bold=True, color="FFFFFF", size=11)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
        thin_border  = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        ws.row_dimensions[1].height = 28
        for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.fill = header_fill; cell.font = header_font
            cell.alignment = center_align; cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = w
        alt_fill = PatternFill("solid", fgColor="FEF9F9")
        for row_idx, res in enumerate(results, start=2):
            ws.row_dimensions[row_idx].height = 20
            fill = alt_fill if row_idx % 2 == 0 else PatternFill()
            for col_idx, val in enumerate([
                row_idx-1, res.get("브랜드",""), res.get("상품명",""), res.get("판매가",""),
                res.get("색상",""), res.get("사이즈",""), res.get("모델번호",""),
                res.get("URL",""), res.get("상품상세이미지",""), res.get("오류",""),
            ], start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border = thin_border
                cell.alignment = center_align if col_idx == 1 else left_align
                if fill.fill_type: cell.fill = fill
        buf = BytesIO(); wb.save(buf); buf.seek(0)
        return buf

    excel_buf = build_excel(st.session_state.results)
    st.markdown("&nbsp;")
    st.download_button(
        label="📥 Excel 다운로드",
        data=excel_buf,
        file_name="ssg_products.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 상품상세 이미지 미리보기
    has_images = any(r.get("상품상세이미지") for r in st.session_state.results)
    if has_images:
        st.markdown("---")
        st.subheader("🖼️ 상품상세 이미지 미리보기")

        IMG_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.ssg.com/",
        }

        for res in st.session_state.results:
            img_block = res.get("상품상세이미지", "").strip()
            if not img_block:
                continue

            st.markdown(
                f'<div class="product-header">'
                f'<b>{res.get("브랜드","")} | {res.get("상품명","")}</b>'
                f'<div class="product-meta">모델번호: {res.get("모델번호","")} &nbsp;|&nbsp; 판매가: {res.get("판매가","")}원</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            for img_url in [u.strip() for u in img_block.splitlines() if u.strip()]:
                try:
                    resp = requests.get(img_url, headers=IMG_HEADERS, timeout=15)
                    resp.raise_for_status()
                    st.image(BytesIO(resp.content), use_container_width=True)
                except Exception:
                    st.caption(f"⚠ 이미지 로드 실패: {img_url[:80]}")
