#!/bin/bash

echo "국책과제 Expert AI 가상환경을 활성화합니다..."

# 가상환경이 존재하는지 확인
if [ ! -d ".venv" ]; then
    echo "가상환경이 존재하지 않습니다. 먼저 install_packages.sh를 실행하세요."
    exit 1
fi

# 가상환경 활성화
source .venv/bin/activate

echo "가상환경이 활성화되었습니다."
echo "현재 Python 경로: $VIRTUAL_ENV/bin/python"
echo ""
echo "설치된 패키지 목록:"
pip list

echo ""
echo "애플리케이션을 실행하려면 다음 명령어를 입력하세요:"
echo "streamlit run app.py"

# 현재 쉘에서 계속 실행
exec $SHELL 