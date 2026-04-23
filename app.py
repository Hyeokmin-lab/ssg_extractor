"""
SSG.COM 상품 정보 추출기 - Streamlit UI
"""

import streamlit as st
import pandas as pd
from io import BytesIO
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
    hr { margin: 1.2rem 0 !important; }

    /* 진행 상태 박스 */
    .status-box {
        background: #f0f4ff; border-left: 4px solid #3b82f6;
        padding: 10px 14px; border-radius: 4px;
        font-size: 0.875rem; color: #1e40af; margin: 8px 0;
    }

    /* 상품 카드 */
    .product-card {
        border: 1px solid #e5e7eb; border-radius: 10px;
        padding: 18px 20px; margin: 20px 0;
        background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .product-card-title {
        font-size: 1rem; font-weight: 700; color: #111;
        border-bottom: 2px solid #e74c3c;
        padding-bottom: 8px; margin-bottom: 12px;
    }
    .product-no {
        display: inline-block; background: #e74c3c; color: #fff;
        font-size: 0.75rem; font-weight: 700;
        border-radius: 4px; padding: 2px 8px; margin-right: 8px;
    }
    .info-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-bottom: 14px; }
    .info-table th {
        width: 90px; background: #f3f4f6; color: #555;
        font-weight: 600; padding: 7px 10px;
        border: 1px solid #e5e7eb; text-align: left;
    }
    .info-table td { padding: 7px 10px; border: 1px solid #e5e7eb; color: #222; }
    .section-label {
        font-size: 0.8rem; font-weight: 700; color: #888;
        text-transform: uppercase; letter-spacing: 0.05em;
        margin: 14px 0 6px 0;
    }
    .img-divider { border: none; border-top: 1px dashed #e5e7eb; margin: 14px 0; }
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
    label="urls", label_visibility="collapsed",
    placeholder="URL을 한 줄에 하나씩 입력하세요.\n(예: https://www.ssg.com/item/itemView.ssg?itemId=1000795246042)",
    height=160, key="url_textarea",
)
st.markdown("---")

# 버튼
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
        results = []
        log_msgs = []

        def update_log(msg):
            log_msgs.append(msg)
            log_area.markdown("\n".join(f"- {m}" for m in log_msgs[-5:]), unsafe_allow_html=True)

        driver = create_driver(headless=True)
        try:
            for idx, url in enumerate(raw_urls):
                status_box.markdown(
                    f'<div class="status-box">⏳ 처리 중... ({idx+1} / {len(raw_urls)}) '
                    f'<code>{url[:65]}</code></div>',
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
                time.sleep(0.3)
        finally:
            driver.quit()

        st.session_state.results  = results
        st.session_state.log_msgs = log_msgs
        status_box.markdown(
            f'<div class="status-box" style="border-color:#22c55e;background:#f0fdf4;color:#15803d;">'
            f"✅ 완료! 총 {len(results)}개 상품 추출 완료</div>",
            unsafe_allow_html=True,
        )

# ── 결과 카드 표시 ────────────────────────────────────────────────
if st.session_state.results:
    st.markdown("---")
    st.subheader(f"📋 추출 결과 ({len(st.session_state.results)}개)")

    IMG_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.ssg.com/",
    }

    def load_image(url):
        try:
            resp = requests.get(url, headers=IMG_HEADERS, timeout=15)
            resp.raise_for_status()
            return BytesIO(resp.content)
        except Exception:
            return None

    for i, res in enumerate(st.session_state.results, start=1):
        # 카드 헤더
        st.markdown(
            f'<div class="product-card">'
            f'<div class="product-card-title">'
            f'<span class="product-no">#{i}</span>'
            f'{res.get("브랜드", "")} | {res.get("상품명", "")}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 정보 테이블
        fields = [
            ("브랜드",   res.get("브랜드", "")),
            ("상품명",   res.get("상품명", "")),
            ("판매가",   f'{res.get("판매가", "")}원' if res.get("판매가") else ""),
            ("색상",     res.get("색상", "")),
            ("사이즈",   res.get("사이즈", "")),
            ("모델번호", res.get("모델번호", "")),
            ("URL",     f'<a href="{res.get("URL","")}" target="_blank">링크 열기</a>' if res.get("URL") else ""),
        ]
        rows = "".join(
            f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in fields
        )
        st.markdown(
            f'<table class="info-table">{rows}</table></div>',
            unsafe_allow_html=True,
        )

        # 대표이미지 (복수)
        main_block = res.get("대표이미지", "").strip()
        if main_block:
            main_urls = [u.strip() for u in main_block.splitlines() if u.strip()]
            st.markdown(
                f'<p class="section-label">🏷 대표이미지 ({len(main_urls)}장)</p>',
                unsafe_allow_html=True,
            )
            cols = st.columns(min(len(main_urls), 4))
            for j, img_url in enumerate(main_urls):
                img_data = load_image(img_url)
                with cols[j % len(cols)]:
                    if img_data:
                        st.image(img_data, use_container_width=True)
                    else:
                        st.caption("⚠ 로드 실패")

        # 상품상세 이미지
        detail_block = res.get("상품상세이미지", "").strip()
        if detail_block:
            detail_urls = [u.strip() for u in detail_block.splitlines() if u.strip()]
            st.markdown(
                f'<hr class="img-divider"><p class="section-label">🖼 상품상세 이미지 ({len(detail_urls)}장)</p>',
                unsafe_allow_html=True,
            )
            for img_url in detail_urls:
                img_data = load_image(img_url)
                if img_data:
                    st.image(img_data, use_container_width=True)
                else:
                    st.caption(f"⚠ 로드 실패: {img_url[:70]}")

        if res.get("오류"):
            st.error(f"오류: {res['오류']}")

        st.markdown("---")
