@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   SSG.COM 상품 정보 추출기 시작
echo ========================================
echo.

cd /d "%~dp0"

:: 가상환경 확인 및 생성
if not exist ".venv\Scripts\activate.bat" (
    echo [설치] 가상환경 생성 중...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

:: 패키지 설치
pip install -r requirements.txt --quiet

echo.
echo [실행] Streamlit 앱 시작...
echo 브라우저에서 http://localhost:8502 로 접속하세요.
echo.
streamlit run app.py --server.port 8502 --server.headless true

pause
