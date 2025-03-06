#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
국책과제 Expert AI 환경 설정 스크립트
이 스크립트는 필요한 패키지를 확인하고 설치합니다.
"""

import os
import sys
import subprocess
import platform
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('setup.log')
    ]
)

# 필요한 패키지 목록
REQUIRED_PACKAGES = [
    "pyhwpx==0.44.1",
    "langchain==0.3.19",
    "langchain-google-genai==2.0.11",
    "streamlit==1.32.0",
    "python-dotenv==1.0.0",
    "google-generativeai==0.4.0",
    "pandas==2.2.0",
    "requests==2.31.0",
    "openai==1.1.0",
    "langchain-anthropic==0.2.1",
    "langchain-openai==0.2.1",
    "langchain-community==0.2.1",
    "langchain-core==0.2.1",
]

# Windows 환경에서만 필요한 패키지
if platform.system() == "Windows":
    REQUIRED_PACKAGES.append("pywin32==308")

def check_venv():
    """가상환경이 활성화되어 있는지 확인합니다."""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def create_venv():
    """가상환경을 생성합니다."""
    venv_path = Path(".venv")
    if venv_path.exists():
        logging.info("가상환경이 이미 존재합니다.")
        return True
    
    logging.info("가상환경을 생성합니다...")
    try:
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        logging.info("가상환경이 성공적으로 생성되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"가상환경 생성 중 오류가 발생했습니다: {e}")
        return False

def activate_venv():
    """가상환경을 활성화합니다."""
    if check_venv():
        logging.info("가상환경이 이미 활성화되어 있습니다.")
        return True
    
    venv_path = Path(".venv")
    if not venv_path.exists():
        if not create_venv():
            return False
    
    # 가상환경 활성화 방법 안내
    if platform.system() == "Windows":
        activate_script = venv_path / "Scripts" / "activate.bat"
        logging.info(f"다음 명령어로 가상환경을 활성화하세요: {activate_script}")
        logging.info("또는 'activate_venv.bat' 스크립트를 실행하세요.")
    else:
        activate_script = venv_path / "bin" / "activate"
        logging.info(f"다음 명령어로 가상환경을 활성화하세요: source {activate_script}")
        logging.info("또는 'source activate_venv.sh' 스크립트를 실행하세요.")
    
    return False

def install_packages():
    """필요한 패키지를 설치합니다."""
    if not check_venv():
        logging.warning("가상환경이 활성화되어 있지 않습니다. 패키지 설치 전에 가상환경을 활성화하세요.")
        return False
    
    logging.info("pip를 업그레이드합니다...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"pip 업그레이드 중 오류가 발생했습니다: {e}")
        return False
    
    logging.info("필요한 패키지를 설치합니다...")
    try:
        for package in REQUIRED_PACKAGES:
            logging.info(f"{package} 설치 중...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
        logging.info("모든 패키지가 성공적으로 설치되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"패키지 설치 중 오류가 발생했습니다: {e}")
        return False

def check_env_file():
    """환경 변수 파일을 확인합니다."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        logging.info(".env 파일이 이미 존재합니다.")
        return True
    
    if env_example.exists():
        logging.info(".env.example 파일을 .env 파일로 복사합니다.")
        try:
            with open(env_example, 'r', encoding='utf-8') as src:
                with open(env_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            logging.info(".env 파일이 생성되었습니다. API 키를 설정하세요.")
            return True
        except Exception as e:
            logging.error(f".env 파일 생성 중 오류가 발생했습니다: {e}")
            return False
    else:
        logging.warning(".env.example 파일이 존재하지 않습니다.")
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("# API 키 설정\n")
                f.write("GOOGLE_API_KEY=your_google_api_key_here\n")
                f.write("PERPLEXITY_API_KEY=your_perplexity_api_key_here\n")
            logging.info(".env 파일이 생성되었습니다. API 키를 설정하세요.")
            return True
        except Exception as e:
            logging.error(f".env 파일 생성 중 오류가 발생했습니다: {e}")
            return False

def main():
    """메인 함수"""
    logging.info("국책과제 Expert AI 환경 설정을 시작합니다...")
    
    # 가상환경 확인 및 활성화
    if not check_venv():
        if not create_venv():
            logging.error("가상환경 생성에 실패했습니다. 설정을 중단합니다.")
            return
        
        if not activate_venv():
            logging.warning("가상환경을 활성화한 후 이 스크립트를 다시 실행하세요.")
            return
    
    # 패키지 설치
    if not install_packages():
        logging.error("패키지 설치에 실패했습니다. 설정을 중단합니다.")
        return
    
    # 환경 변수 파일 확인
    if not check_env_file():
        logging.error("환경 변수 파일 설정에 실패했습니다.")
        return
    
    logging.info("환경 설정이 완료되었습니다.")
    logging.info("애플리케이션을 실행하려면 'streamlit run app.py' 명령어를 입력하세요.")

if __name__ == "__main__":
    main() 