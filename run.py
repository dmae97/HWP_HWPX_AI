#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import platform
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger("run")

def check_dependencies():
    """필요한 패키지가 설치되어 있는지 확인합니다."""
    required_packages = [
        "pyhwpx",
        "langchain",
        "langchain-google-genai",
        "streamlit",
        "python-dotenv",
        "google-generativeai",
        "pandas",
        "requests"
    ]
    
    if platform.system() == "Windows":
        required_packages.append("pywin32")
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"다음 패키지가 설치되어 있지 않습니다: {', '.join(missing_packages)}")
        
        install = input("누락된 패키지를 설치하시겠습니까? (y/n): ")
        if install.lower() == "y":
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
                logger.info("패키지 설치가 완료되었습니다.")
            except subprocess.CalledProcessError as e:
                logger.error(f"패키지 설치 중 오류가 발생했습니다: {str(e)}")
                return False
        else:
            logger.warning("필요한 패키지가 설치되어 있지 않아 애플리케이션이 제대로 작동하지 않을 수 있습니다.")
    
    return True

def check_api_keys():
    """API 키가 설정되어 있는지 확인합니다."""
    # .env 파일 로드
    load_dotenv()
    
    # API 키 확인
    google_api_key = os.getenv("GOOGLE_API_KEY")
    perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
    
    if not google_api_key:
        logger.warning("Google API 키가 설정되어 있지 않습니다.")
        
        api_key = input("Google API 키를 입력하세요 (Enter 키를 누르면 건너뜁니다): ")
        if api_key:
            # .env 파일에 API 키 추가
            env_path = Path(".env")
            
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    env_content = f.read()
                
                if "GOOGLE_API_KEY" in env_content:
                    env_content = env_content.replace(
                        f"GOOGLE_API_KEY={google_api_key or ''}",
                        f"GOOGLE_API_KEY={api_key}"
                    )
                else:
                    env_content += f"\nGOOGLE_API_KEY={api_key}\n"
            else:
                env_content = f"GOOGLE_API_KEY={api_key}\n"
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # 환경 변수 설정
            os.environ["GOOGLE_API_KEY"] = api_key
            logger.info("Google API 키가 설정되었습니다.")
    
    if not perplexity_api_key:
        logger.warning("Perplexity API 키가 설정되어 있지 않습니다.")
        
        api_key = input("Perplexity API 키를 입력하세요 (Enter 키를 누르면 건너뜁니다): ")
        if api_key:
            # .env 파일에 API 키 추가
            env_path = Path(".env")
            
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    env_content = f.read()
                
                if "PERPLEXITY_API_KEY" in env_content:
                    env_content = env_content.replace(
                        f"PERPLEXITY_API_KEY={perplexity_api_key or ''}",
                        f"PERPLEXITY_API_KEY={api_key}"
                    )
                else:
                    env_content += f"\nPERPLEXITY_API_KEY={api_key}\n"
            else:
                env_content = f"PERPLEXITY_API_KEY={api_key}\n"
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # 환경 변수 설정
            os.environ["PERPLEXITY_API_KEY"] = api_key
            logger.info("Perplexity API 키가 설정되었습니다.")
    
    return True

def check_data_directory():
    """데이터 디렉토리가 존재하는지 확인하고 없으면 생성합니다."""
    data_dir = Path("data")
    
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("데이터 디렉토리가 생성되었습니다.")
    
    return True

def run_app():
    """Streamlit 애플리케이션을 실행합니다."""
    try:
        logger.info("애플리케이션을 시작합니다...")
        
        # Streamlit 실행
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
        
        return True
    except Exception as e:
        logger.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("=" * 50)
    print("국책과제 Expert AI 시작하기")
    print("=" * 50)
    
    # 의존성 확인
    if not check_dependencies():
        print("\n오류: 필요한 패키지가 설치되어 있지 않습니다.")
        print("requirements.txt 파일을 확인하고 'pip install -r requirements.txt' 명령을 실행하세요.")
        return
    
    # API 키 확인
    if not check_api_keys():
        print("\n경고: API 키가 설정되어 있지 않습니다.")
        print("애플리케이션 내에서 API 키를 설정할 수 있습니다.")
    
    # 데이터 디렉토리 확인
    if not check_data_directory():
        print("\n경고: 데이터 디렉토리를 생성할 수 없습니다.")
    
    # 애플리케이션 실행
    print("\n애플리케이션을 시작합니다...")
    time.sleep(1)
    
    if not run_app():
        print("\n오류: 애플리케이션을 실행할 수 없습니다.")
        return
    
    print("\n애플리케이션이 종료되었습니다.")

if __name__ == "__main__":
    main() 