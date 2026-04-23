"""
SSG.COM 상품 정보 추출기 - 핵심 모듈
"""

import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)


def create_driver(headless=True):
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def _safe_text(driver, css, default=""):
    try:
        return driver.find_element(By.CSS_SELECTOR, css).text.strip()
    except Exception:
        return default


def extract_product(driver, url, status_callback=None):
    """
    SSG.COM 단일 상품 페이지에서 정보를 추출합니다.
    반환값: dict
    """

    def log(msg):
        if status_callback:
            status_callback(msg)

    result = {
        "URL": url,
        "브랜드": "",
        "상품명": "",
        "판매가": "",
        "색상": "",
        "사이즈": "",
        "모델번호": "",
        "상품상세이미지": "",
        "오류": "",
    }

    try:
        driver.get(url)
        time.sleep(3)

        # ── 브랜드 ──────────────────────────────────────────────
        # <a href="..." class="cdtl_info_tit_link">K2</a>
        try:
            el = driver.find_element(By.CSS_SELECTOR, "a.cdtl_info_tit_link")
            brand_text = el.text.strip()
            # <i> 태그(화살표 아이콘) 텍스트 제거
            result["브랜드"] = re.sub(r"\s*\uf105\s*", "", brand_text).strip()
        except Exception:
            log("⚠ 브랜드 추출 실패")

        # ── 상품명 ──────────────────────────────────────────────
        # <span class="cdtl_info_tit_txt">...</span>
        try:
            el = driver.find_element(By.CSS_SELECTOR, "span.cdtl_info_tit_txt")
            result["상품명"] = el.text.strip()
        except Exception:
            log("⚠ 상품명 추출 실패")

        # ── 판매가 ──────────────────────────────────────────────
        # 할인내역 툴팁 dl 목록에서 dt="판매가" 행의 가격 우선 추출
        price_found = False
        try:
            dls = driver.find_elements(By.CSS_SELECTOR, "dl.cdtl_ly_dl")
            for dl in dls:
                try:
                    dt_text = dl.find_element(By.TAG_NAME, "dt").text.strip()
                    if dt_text == "판매가":
                        em = dl.find_element(By.CSS_SELECTOR, "em.ssg_price")
                        raw = em.text.strip().replace(",", "").replace("원", "")
                        result["판매가"] = raw
                        price_found = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # fallback 1: .cdtl_old_price (할인 있을 때 정가 표시 영역)
        if not price_found:
            try:
                el = driver.find_element(
                    By.CSS_SELECTOR, ".cdtl_old_price em.ssg_price"
                )
                result["판매가"] = (
                    el.text.strip().replace(",", "").replace("원", "")
                )
                price_found = True
            except Exception:
                pass

        # fallback 2: 메인 노출 가격
        if not price_found:
            try:
                el = driver.find_element(
                    By.CSS_SELECTOR, ".cdtl_new_price em.ssg_price"
                )
                result["판매가"] = (
                    el.text.strip().replace(",", "").replace("원", "")
                )
            except Exception:
                log("⚠ 판매가 추출 실패")

        # ── 모델번호 ─────────────────────────────────────────────
        # <p class="cdtl_model_num">모델번호 : KWM26142</p>
        try:
            el = driver.find_element(By.CSS_SELECTOR, "p.cdtl_model_num")
            result["모델번호"] = re.sub(r"^모델번호\s*:\s*", "", el.text.strip())
        except Exception:
            log("⚠ 모델번호 추출 실패")

        # ── 색상 (ordOpt1) ────────────────────────────────────────
        colors = []
        try:
            sel_el = driver.find_element(By.ID, "ordOpt1")
            opts = sel_el.find_elements(By.CSS_SELECTOR, "option")
            for opt in opts:
                val = opt.get_attribute("value")
                if val:
                    colors.append(val)
        except Exception:
            log("⚠ 색상 추출 실패")

        result["색상"] = ", ".join(colors)

        # ── 사이즈 (ordOpt2, 색상 선택 후 동적 로딩) ─────────────
        all_sizes = []
        if colors:
            for color_val in colors:
                try:
                    # JS로 hidden select 값 변경 및 change 이벤트 발생
                    driver.execute_script(
                        """
                        var sel = document.getElementById('ordOpt1');
                        if (sel) {
                            sel.value = arguments[0];
                            sel.dispatchEvent(new Event('change', {bubbles: true}));
                            if (typeof ItmOp !== 'undefined') {
                                ItmOp.changeUitemIptn(sel);
                            }
                        }
                        """,
                        color_val,
                    )
                    time.sleep(1.8)  # AJAX 응답 대기

                    size_sel_el = driver.find_element(By.ID, "ordOpt2")
                    size_opts = size_sel_el.find_elements(
                        By.CSS_SELECTOR, "option"
                    )
                    for opt in size_opts:
                        val = opt.get_attribute("value")
                        if val and val not in all_sizes:
                            all_sizes.append(val)
                except Exception:
                    continue

        result["사이즈"] = ", ".join(all_sizes)

        # ── 상품상세 이미지 URL ────────────────────────────────────
        # div.cdtl_sec.cdtl_seller_html 내부 img 태그 src 수집
        try:
            detail_div = driver.find_element(
                By.CSS_SELECTOR, "div.cdtl_sec.cdtl_seller_html"
            )
            imgs = detail_div.find_elements(By.TAG_NAME, "img")
            img_urls = []
            for img in imgs:
                src = (
                    img.get_attribute("src")
                    or img.get_attribute("data-src")
                    or img.get_attribute("data-original")
                    or ""
                ).strip()
                # 유효한 http URL이고 중복 아닌 경우만
                if src and src.startswith("http") and src not in img_urls:
                    # 썸네일/아이콘 제외 (필요시 조건 추가)
                    img_urls.append(src)
            result["상품상세이미지"] = "\n".join(img_urls)
        except Exception:
            log("⚠ 상품상세이미지 추출 실패")

    except Exception as e:
        result["오류"] = str(e)
        log(f"❌ 오류: {e}")

    return result
