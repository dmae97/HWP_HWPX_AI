@echo off
echo 국책과제 Expert AI 패키지 설치를 시작합니다...

REM 가상환경이 존재하는지 확인
if not exist .venv (
    echo 가상환경이 존재하지 않습니다. 먼저 가상환경을 생성합니다.
    python -m venv .venv
    if errorlevel 1 (
        echo 가상환경 생성에 실패했습니다.
        echo Python이 올바르게 설치되어 있는지 확인하세요.
        echo 수동으로 다음 명령어를 실행해보세요: python -m venv .venv
        pause
        exit /b 1
    )
    echo 가상환경이 생성되었습니다.
)

REM 가상환경 활성화 및 패키지 설치
echo 가상환경을 활성화하고 패키지를 설치합니다...
call .venv\Scripts\activate.bat

REM pip 업그레이드
echo pip를 업그레이드합니다...
python -m pip install --upgrade pip

REM 패키지 설치
echo 필요한 패키지를 설치합니다...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo 패키지 설치 중 오류가 발생했습니다.
    echo 일부 패키지가 설치되지 않았을 수 있습니다.
    echo 다음 명령어로 개별 패키지를 설치해보세요:
    echo.
    echo pip install pyhwpx==0.44.1
    echo pip install langchain==0.3.19
    echo pip install langchain-google-genai==2.0.11
    echo pip install streamlit==1.32.0
    echo pip install python-dotenv==1.0.0
    echo pip install google-generativeai==0.4.0
    echo pip install pandas==2.2.0
    echo pip install requests==2.31.0
    echo pip install pywin32==308
    echo pip install openai==1.1.0
    echo pip install langchain-anthropic==0.2.1
    echo pip install langchain-openai==0.2.1
    echo pip install langchain-community==0.2.1
    echo pip install langchain-core==0.2.1
    echo.
    echo 자세한 내용은 SETUP_GUIDE.md 파일을 참조하세요.
    pause
    exit /b 1
)

echo 패키지 설치가 완료되었습니다.
echo.
echo 설치된 패키지 목록:
pip list

REM 가상환경 비활성화
call deactivate

echo.
echo 설치가 완료되었습니다. 'activate_venv.bat'를 실행하여 가상환경을 활성화할 수 있습니다.
pause 