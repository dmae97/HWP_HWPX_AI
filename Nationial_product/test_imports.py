"""
가져오기 테스트 스크립트

이 스크립트는 필요한 모듈이 제대로 설치되었는지 확인합니다.
"""

print("모듈 가져오기 테스트를 시작합니다...")

# 기본 모듈
import os
import sys
import tempfile
import logging

print(f"Python 버전: {sys.version}")
print(f"Python 경로: {sys.executable}")

# 필수 모듈 가져오기 시도
try:
    import pyhwpx
    print("✓ pyhwpx 모듈 가져오기 성공")
except ImportError as e:
    print(f"✗ pyhwpx 모듈 가져오기 실패: {e}")

try:
    import dotenv
    print("✓ dotenv 모듈 가져오기 성공")
except ImportError as e:
    print(f"✗ dotenv 모듈 가져오기 실패: {e}")

try:
    import win32com.client
    print("✓ win32com.client 모듈 가져오기 성공")
except ImportError as e:
    print(f"✗ win32com.client 모듈 가져오기 실패: {e}")

try:
    import google.generativeai
    print(f"✓ google.generativeai 모듈 가져오기 성공 (버전: {google.generativeai.__version__})")
except ImportError as e:
    print(f"✗ google.generativeai 모듈 가져오기 실패: {e}")

try:
    import langchain
    print(f"✓ langchain 모듈 가져오기 성공 (버전: {langchain.__version__})")
except ImportError as e:
    print(f"✗ langchain 모듈 가져오기 실패: {e}")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    print("✓ langchain.text_splitter 모듈 가져오기 성공")
except ImportError as e:
    print(f"✗ langchain.text_splitter 모듈 가져오기 실패: {e}")

try:
    import langchain_google_genai
    print(f"✓ langchain_google_genai 모듈 가져오기 성공")
except ImportError as e:
    print(f"✗ langchain_google_genai 모듈 가져오기 실패: {e}")

print("\n테스트 결과 요약:")
print("------------------------------")
print("모든 테스트가 완료되었습니다. 실패한 가져오기가 있는지 확인하고 필요한 패키지를 설치하세요.")
print("패키지 설치 명령어: pip install -r requirements.txt")
print("------------------------------") 