@echo off
echo 국책과제 Expert AI 가상환경을 활성화합니다...

REM 가상환경이 존재하는지 확인
if not exist .venv (
    echo 가상환경이 존재하지 않습니다. 먼저 install_packages.bat를 실행하세요.
    exit /b 1
)

REM 가상환경 활성화
call .venv\Scripts\activate.bat

echo 가상환경이 활성화되었습니다.
echo 현재 Python 경로: %VIRTUAL_ENV%\Scripts\python.exe
echo.
echo 설치된 패키지 목록:
pip list

echo.
echo 애플리케이션을 실행하려면 다음 명령어를 입력하세요:
echo streamlit run app.py

REM 명령 프롬프트 유지
cmd /k 