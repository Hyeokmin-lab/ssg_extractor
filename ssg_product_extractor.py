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


def _build_options(headless=True):
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # Cloud 환경에서 메모리 제한 대응
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=9222")
    return options


def create_driver(headless=True):
    """
    실행 환경에 따라 자동으로 ChromeDriver를 선택합니다.
    - Streamlit Cloud / Linux: 시스템 Chromium 사용
    - 로컬 Windows/Mac: webdriver-manager 자동 다운로드
    """
    import os
    import shutil
    from selenium.webdriver.chrome.service import Service

    options = _build_options(headless)

    # ── Streamlit Cloud (Linux) 환경 감지 ──────────────────────
    # packages.txt 로 설치된 chromium-driver 경로 사용
    CLOUD_DRIVER_PATHS = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
        "/usr/lib/chromium/chromedriver",
    ]
    CLOUD_BINARY_PATHS = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/lib/chromium-browser/chromium-browser",
    ]

    cloud_driver = next((p for p in CLOUD_DRIVER_PATHS if os.path.exists(p)), None)
    cloud_binary = next((p for p in CLOUD_BINARY_PATHS if os.path.exists(p)), None)

    if cloud_driver:
        # Cloud 환경
        if cloud_binary:
            options.binary_location = cloud_binary
        driver = webdriver.Chrome(
            service=Service(executable_path=cloud_driver), options=options
        )
    else:
        # 로컬 환경 → webdriver-manager 자동 설치
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=options
            )
        except Exception as e:
            raise RuntimeError(
                f"ChromeDriver 초기화 실패: {e}\n"
                "Chrome이 설치되어 있는지 확인하거나, packages.txt에 chromium/chromium-driver를 추가하세요."
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
        "대표이미지": "",
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
        # .cdtl_new_price > em.ssg_price (실제 노출 판매가)
        try:
            el = driver.find_element(
                By.CSS_SELECTOR, ".cdtl_new_price em.ssg_price"
            )
            result["판매가"] = el.text.strip().replace(",", "").replace("원", "")
        except Exception:
            log("⚠ 판매가 추출 실패")

        # ── 모델번호 ─────────────────────────────────────────────
        # <p class="cdtl_model_num">모델번호 : KWM26142</p>
        try:
            el = driver.find_element(By.CSS_SELECTOR, "p.cdtl_model_num")
            result["모델번호"] = re.sub(r"^모델번호\s*:\s*", "", el.text.strip())
        except Exception:
            log("⚠ 모델번호 추출 실패")

        # ── 옵션 그룹 공통 영역 ───────────────────────────────────
        # #_ordOpt_area 안에 cdtl_opt_group 이 색상/사이즈 순서로 있음
        opt_groups = driver.find_elements(
            By.CSS_SELECTOR, "#_ordOpt_area .cdtl_opt_group"
        )
        color_group = opt_groups[0] if len(opt_groups) > 0 else None
        size_group  = opt_groups[1] if len(opt_groups) > 1 else None

        # ── 색상 ──────────────────────────────────────────────────
        colors = []
        try:
            color_sel_el = driver.find_element(By.ID, "ordOpt1")
            for opt in color_sel_el.find_elements(By.CSS_SELECTOR, "option"):
                val = opt.get_attribute("value")
                if val:
                    colors.append(val)
        except Exception:
            log("⚠ 색상 select 접근 실패")

        result["색상"] = ", ".join(colors)

        # ── 사이즈 (커스텀 드롭다운 직접 클릭) ──────────────────
        # SSG는 ssg_react_v2.direct_call() 기반 커스텀 드롭다운이라
        # hidden select에 JS change 이벤트를 쏘는 방식은 동작하지 않음.
        # 실제 눈에 보이는 <li> 항목을 JS click()으로 눌러야 함.
        all_sizes = []

        if color_group and colors:
            # 색상 개수만 먼저 파악 (DOM 참조 없이 index로 순회)
            color_count = len(color_group.find_elements(
                By.CSS_SELECTOR, ".cdtl_select_lst li"
            ))

            for idx in range(color_count):
                try:
                    # 매 반복마다 DOM 재조회 → StaleElement 방지
                    color_group = driver.find_elements(
                        By.CSS_SELECTOR, "#_ordOpt_area .cdtl_opt_group"
                    )[0]
                    size_group = driver.find_elements(
                        By.CSS_SELECTOR, "#_ordOpt_area .cdtl_opt_group"
                    )[1] if len(driver.find_elements(
                        By.CSS_SELECTOR, "#_ordOpt_area .cdtl_opt_group"
                    )) > 1 else None

                    # 드롭다운 토글 버튼 클릭해서 열기
                    drop_btn = color_group.find_element(
                        By.CSS_SELECTOR, "a._drop_select"
                    )
                    driver.execute_script("arguments[0].click();", drop_btn)
                    time.sleep(0.4)

                    # 색상 <li> 목록 재조회 후 해당 인덱스 클릭
                    color_lis = color_group.find_elements(
                        By.CSS_SELECTOR, ".cdtl_select_lst li"
                    )
                    link = color_lis[idx].find_element(By.CSS_SELECTOR, "a.clickable")
                    driver.execute_script("arguments[0].click();", link)
                    time.sleep(2.0)   # AJAX 사이즈 로딩 대기

                    # hidden select#ordOpt2 에서 사이즈 수집
                    try:
                        size_sel_el = driver.find_element(By.ID, "ordOpt2")
                        for opt in size_sel_el.find_elements(By.CSS_SELECTOR, "option"):
                            val = opt.get_attribute("value")
                            if val and val not in all_sizes:
                                all_sizes.append(val)
                    except Exception:
                        pass

                    # fallback: 커스텀 사이즈 리스트에서 읽기
                    if size_group:
                        size_lis = size_group.find_elements(
                            By.CSS_SELECTOR, ".cdtl_select_lst li"
                        )
                        for sli in size_lis:
                            try:
                                txt = sli.find_element(
                                    By.CSS_SELECTOR, "span.txt"
                                ).text.strip()
                                if txt and txt not in all_sizes:
                                    all_sizes.append(txt)
                            except Exception:
                                pass

                except Exception as e:
                    log(f"⚠ 색상 클릭 중 오류 (index {idx}): {e}")
                    continue

        result["사이즈"] = ", ".join(all_sizes)

        # ── 대표이미지 ─────────────────────────────────────────────
        # #mainImg → .cdtl_img_area img 순으로 시도
        try:
            for sel in ["#mainImg", ".cdtl_img_area img", ".cdtl_img img"]:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    src = (el.get_attribute("src") or el.get_attribute("data-src") or "").strip()
                    if src and src.startswith("http"):
                        result["대표이미지"] = src
                        break
                except Exception:
                    continue
        except Exception:
            log("⚠ 대표이미지 추출 실패")

        # ── 상품상세 이미지 ────────────────────────────────────────
        # div.cdtl_sec.cdtl_seller_html — lazy load 대응: 스크롤 후 수집
        try:
            detail_div = driver.find_element(
                By.CSS_SELECTOR, "div.cdtl_sec.cdtl_seller_html"
            )
            # 상세 영역까지 천천히 스크롤해서 lazy load 트리거
            detail_top = driver.execute_script(
                "return arguments[0].getBoundingClientRect().top + window.scrollY", detail_div
            )
            detail_h = driver.execute_script("return arguments[0].scrollHeight", detail_div)
            step = max(400, detail_h // 10)
            pos = detail_top
            while pos < detail_top + detail_h:
                driver.execute_script(f"window.scrollTo(0, {pos})")
                time.sleep(0.3)
                pos += step
            driver.execute_script(f"window.scrollTo(0, {detail_top + detail_h})")
            time.sleep(1.5)  # 마지막 이미지 로드 대기

            # 스크롤 후 img src 재수집
            imgs = detail_div.find_elements(By.TAG_NAME, "img")
            img_urls = []
            for img in imgs:
                src = (
                    img.get_attribute("src")
                    or img.get_attribute("data-src")
                    or img.get_attribute("data-original")
                    or ""
                ).strip()
                if src and src.startswith("http") and src not in img_urls:
                    img_urls.append(src)
            result["상품상세이미지"] = "\n".join(img_urls)

        except Exception:
            log("⚠ 상품상세이미지 추출 실패")

    except Exception as e:
        result["오류"] = str(e)
        log(f"❌ 오류: {e}")

    return result
