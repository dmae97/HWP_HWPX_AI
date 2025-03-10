"""
가져오기 테스트 스크립트

이 스크립트는 필요한 모듈이 제대로 설치되었는지 확인합니다.
"""

import os
import sys
import platform
import tempfile
import logging
from collections import defaultdict

print("모듈 가져오기 테스트를 시작합니다...")

print(f"Python 버전: {sys.version}")
print(f"Python 경로: {sys.executable}")
print(f"운영체제: {platform.system()} {platform.release()}")

# 테스트 결과 저장
results = defaultdict(dict)

# 주요 패키지 목록 
REQUIRED_PACKAGES = [
    ("streamlit", "Streamlit UI"),
    ("dotenv", "환경 변수 관리"),
    ("pandas", "데이터 분석"),
    ("requests", "HTTP 요청"),
    ("olefile", "OLE 파일 처리"),
    ("langchain", "LangChain 기본 패키지"),
    ("langchain_core", "LangChain 코어"),
    ("langchain_text_splitters", "텍스트 분할"),
    ("google.generativeai", "Google Generative AI"),
    ("numpy", "수치 연산"),
    ("PIL", "이미지 처리 (Pillow)"),
    ("tqdm", "진행률 표시"),
    ("matplotlib", "데이터 시각화"),
    ("sklearn", "머신러닝"),
    ("diskcache", "디스크 캐싱"),
    ("reportlab", "PDF 생성"),
    ("mistralai", "Mistral AI API"),
    ("fastapi", "API 서버"),
    ("uvicorn", "ASGI 서버")
]

# Windows 전용 패키지
WINDOWS_PACKAGES = [
    ("win32com", "Windows COM 객체 접근"),
    ("pyhwpx", "HWPX 파일 처리")
]

# 패키지 테스트
for package_name, description in REQUIRED_PACKAGES:
    try:
        module = __import__(package_name)
        version = getattr(module, "__version__", "알 수 없음")
        results["success"][package_name] = f"{description} (버전: {version})"
    except ImportError as e:
        results["fail"][package_name] = f"{description}: {str(e)}"

# 윈도우 전용 패키지 테스트 (Windows 환경에서만)
if platform.system() == "Windows":
    for package_name, description in WINDOWS_PACKAGES:
        try:
            module = __import__(package_name)
            version = getattr(module, "__version__", "알 수 없음")
            results["success"][package_name] = f"{description} (버전: {version})"
        except ImportError as e:
            results["fail"][package_name] = f"{description}: {str(e)}"

# 결과 출력
print("\n테스트 결과 요약:")
print("==============================")
print(f"성공: {len(results['success'])} 패키지")
for package, info in results["success"].items():
    print(f"✓ {package}: {info}")

if results["fail"]:
    print(f"\n실패: {len(results['fail'])} 패키지")
    for package, error in results["fail"].items():
        print(f"✗ {package}: {error}")
    
    print("\n문제 해결 방법:")
    print("1. 가상 환경을 사용하는 경우, 가상 환경이 활성화되었는지 확인하세요.")
    print("2. 다음 명령어로 필요한 패키지를 설치하세요:")
    print("   pip install -r requirements.txt")
    print("3. Windows 사용자는 다음 명령어로 추가 패키지를 설치해야 할 수 있습니다:")
    print("   pip install pywin32==308 pyhwpx==0.44.1")
    print("4. 특정 패키지 설치 오류가 계속되면, 개별적으로 설치해보세요:")
    print("   pip install <패키지명>==<버전>")
else:
    print("\n모든 패키지가 정상적으로 설치되었습니다!")

print("==============================") 