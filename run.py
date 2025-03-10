#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import platform
import time
import signal
import logging
from pathlib import Path
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("run")

def check_dependencies():
    """필요한 패키지가 설치되어 있는지 확인합니다."""
    try:
        import streamlit
        import fastapi
        import uvicorn
        import dotenv
        import mistralai
        return True
    except ImportError as e:
        logger.error(f"필요한 패키지가 설치되어 있지 않습니다: {str(e)}")
        logger.info("pip install -r requirements.txt 명령으로 필요한 패키지를 설치하세요.")
        return False

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

def run_streamlit():
    """Streamlit 앱을 실행합니다."""
    logger.info("Streamlit 앱을 실행합니다...")
    streamlit_process = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.port=8501"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return streamlit_process

def run_fastapi():
    """FastAPI 앱을 실행합니다."""
    logger.info("FastAPI 앱을 실행합니다...")
    fastapi_process = subprocess.Popen(
        ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return fastapi_process

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="HWP & HWPX 파일 분석기 실행 스크립트")
    parser.add_argument("--mode", choices=["streamlit", "api", "both"], default="streamlit",
                      help="실행 모드 (streamlit, api, both)")
    args = parser.parse_args()
    
    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)
    
    # API 키 확인
    if not check_api_keys():
        print("\n경고: API 키가 설정되어 있지 않습니다.")
        print("애플리케이션 내에서 API 키를 설정할 수 있습니다.")
    
    # 데이터 디렉토리 확인
    if not check_data_directory():
        print("\n경고: 데이터 디렉토리를 생성할 수 없습니다.")
    
    # 프로세스 목록
    processes = []
    
    try:
        # 모드에 따라 앱 실행
        if args.mode in ["streamlit", "both"]:
            streamlit_process = run_streamlit()
            processes.append(streamlit_process)
            logger.info("Streamlit 앱이 http://localhost:8501 에서 실행 중입니다.")
        
        if args.mode in ["api", "both"]:
            fastapi_process = run_fastapi()
            processes.append(fastapi_process)
            logger.info("FastAPI 앱이 http://localhost:8000 에서 실행 중입니다.")
            logger.info("API 문서는 http://localhost:8000/docs 에서 확인할 수 있습니다.")
        
        # 프로세스 출력 모니터링
        while True:
            for process in processes:
                output = process.stdout.readline()
                if output:
                    print(output.strip())
                
                error = process.stderr.readline()
                if error:
                    print(f"ERROR: {error.strip()}", file=sys.stderr)
            
            # 프로세스 종료 확인
            if any(process.poll() is not None for process in processes):
                logger.error("프로세스가 예기치 않게 종료되었습니다.")
                break
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료되었습니다.")
    
    finally:
        # 모든 프로세스 종료
        for process in processes:
            if process.poll() is None:  # 프로세스가 아직 실행 중인 경우
                logger.info("프로세스를 종료합니다...")
                if platform.system() == "Windows":
                    process.send_signal(signal.CTRL_C_EVENT)
                else:
                    process.send_signal(signal.SIGINT)
                
                # 정상 종료 대기
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("프로세스가 정상적으로 종료되지 않아 강제 종료합니다.")
                    process.kill()

if __name__ == "__main__":
    main() 