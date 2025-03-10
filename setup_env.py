#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
국책과제 Expert AI 환경 설정 스크립트
이 스크립트는 필요한 패키지를 확인하고 설치합니다.
"""

import os
import sys
import platform
import subprocess
import logging
import tempfile
from pathlib import Path
import time
import re

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("setup.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("setup")

def create_virtual_env():
    """가상 환경을 생성합니다."""
    venv_dir = ".venv"
    
    # 이미 가상 환경이 존재하는지 확인
    if os.path.exists(venv_dir):
        logger.info(f"이미 가상 환경이 존재합니다: {os.path.abspath(venv_dir)}")
        return os.path.abspath(venv_dir)
    
    logger.info("가상 환경을 생성합니다...")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        logger.info(f"가상 환경이 생성되었습니다: {os.path.abspath(venv_dir)}")
        return os.path.abspath(venv_dir)
    except subprocess.CalledProcessError as e:
        logger.error(f"가상 환경 생성 중 오류가 발생했습니다: {str(e)}")
        return None

def get_pip_path(venv_dir):
    """가상 환경의 pip 경로를 반환합니다."""
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
    
    if not os.path.exists(pip_path) and platform.system() == "Windows":
        pip_path += ".exe"
        
    return pip_path

def get_python_path(venv_dir):
    """가상 환경의 Python 인터프리터 경로를 반환합니다."""
    if platform.system() == "Windows":
        python_path = os.path.join(venv_dir, "Scripts", "python")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")
    
    if not os.path.exists(python_path) and platform.system() == "Windows":
        python_path += ".exe"
        
    return python_path

def is_package_installed(python_path, package_name):
    """패키지가 설치되어 있는지 확인합니다."""
    try:
        result = subprocess.run(
            [python_path, "-c", f"import {package_name}; print('ok')"],
            capture_output=True,
            text=True,
            check=False
        )
        return "ok" in result.stdout
    except Exception:
        return False

def update_pip(pip_path):
    """pip를 최신 버전으로 업데이트합니다."""
    logger.info("pip를 최신 버전으로 업데이트합니다...")
    try:
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
        logger.info("pip가 성공적으로 업데이트되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"pip 업데이트 중 오류가 발생했습니다: {str(e)}")
        return False

def install_packages(pip_path, python_path):
    """필요한 패키지를 설치합니다."""
    logger.info("필요한 패키지를 설치합니다...")
    
    # 기본 패키지 설치
    try:
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        logger.info("패키지 설치가 완료되었습니다.")
    except subprocess.CalledProcessError as e:
        logger.error(f"패키지 설치 중 오류가 발생했습니다: {str(e)}")
        
        # 개별 패키지 설치 시도
        logger.info("개별 패키지 설치를 시도합니다...")
        with open("requirements.txt", "r", encoding="utf-8") as f:
            packages = f.readlines()
        
        for package in packages:
            package = package.strip()
            if not package or package.startswith("#"):
                continue
                
            # 조건부 설치 제외 (platform_system 조건이 맞지 않는 경우)
            if "platform_system" in package:
                # Windows 조건 패키지이지만 현재 Windows가 아닌 경우 건너뛰기
                if "Windows" in package and platform.system() != "Windows":
                    continue
                # 비-Windows 조건 패키지이지만 현재 Windows인 경우 건너뛰기
                if "!=" in package and "Windows" in package and platform.system() == "Windows":
                    continue
                    
                # 조건부 문자열 제거
                package = re.sub(r"; platform_system.*", "", package)
            
            logger.info(f"패키지 설치 중: {package}")
            try:
                subprocess.run([pip_path, "install", package], check=True)
            except subprocess.CalledProcessError as e:
                logger.warning(f"패키지 설치 실패: {package}, 오류: {str(e)}")
    
    # 설치 확인
    import_test_script = os.path.join(os.path.dirname(__file__), "test_imports.py")
    if os.path.exists(import_test_script):
        logger.info("패키지 가져오기 테스트를 실행합니다...")
        subprocess.run([python_path, import_test_script], check=False)

def create_env_file():
    """환경 변수 설정 파일을 생성합니다."""
    env_file = ".env"
    
    # 이미 .env 파일이 존재하는지 확인
    if os.path.exists(env_file):
        logger.info(f".env 파일이 이미 존재합니다: {os.path.abspath(env_file)}")
        return
    
    logger.info(".env 파일을 생성합니다...")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("# API 키 설정\n")
        f.write("GOOGLE_API_KEY=\n")
        f.write("MISTRAL_API_KEY=\n")
        f.write("PERPLEXITY_API_KEY=\n")
        f.write("\n# 캐시 설정\n")
        f.write("CACHE_DIR=.cache\n")
        
    logger.info(f".env 파일이 생성되었습니다: {os.path.abspath(env_file)}")
    logger.info("API 키를 입력하려면 .env 파일을 텍스트 편집기로 열어 수정하세요.")

def create_activation_scripts(venv_dir):
    """가상 환경 활성화 스크립트를 생성합니다."""
    venv_dir = os.path.abspath(venv_dir)
    
    # Windows 활성화 배치 파일
    with open("activate_venv.bat", "w", encoding="utf-8") as f:
        f.write(f"@echo off\n")
        f.write(f"echo 가상 환경을 활성화합니다...\n")
        f.write(f"call \"{os.path.join(venv_dir, 'Scripts', 'activate.bat')}\"\n")
        f.write(f"echo 가상 환경이 활성화되었습니다.\n")
        f.write(f"echo Python 경로: %VIRTUAL_ENV%\\Scripts\\python.exe\n")
        f.write(f"cmd /k\n")
    
    # Unix/Linux/Mac 활성화 쉘 스크립트
    with open("activate_venv.sh", "w", encoding="utf-8") as f:
        f.write(f"#!/bin/bash\n")
        f.write(f"echo '가상 환경을 활성화합니다...'\n")
        f.write(f"source \"{os.path.join(venv_dir, 'bin', 'activate')}\"\n")
        f.write(f"echo '가상 환경이 활성화되었습니다.'\n")
        f.write(f"echo 'Python 경로: '$VIRTUAL_ENV'/bin/python'\n")
        f.write(f"exec $SHELL\n")
    
    if platform.system() != "Windows":
        os.chmod("activate_venv.sh", 0o755)  # 실행 권한 부여
    
    logger.info("가상 환경 활성화 스크립트가 생성되었습니다.")
    logger.info("- Windows: activate_venv.bat")
    logger.info("- Linux/Mac: activate_venv.sh")

def main():
    """환경 설정의 메인 함수"""
    logger.info(f"환경 설정을 시작합니다...")
    logger.info(f"Python 버전: {platform.python_version()}")
    logger.info(f"운영체제: {platform.system()} {platform.release()}")
    
    # 가상 환경 생성
    venv_dir = create_virtual_env()
    if not venv_dir:
        logger.error("가상 환경 생성에 실패했습니다. 환경 설정을 종료합니다.")
        return False
    
    # pip 및 Python 경로 가져오기
    pip_path = get_pip_path(venv_dir)
    python_path = get_python_path(venv_dir)
    
    if not os.path.exists(pip_path):
        logger.error(f"pip를 찾을 수 없습니다: {pip_path}")
        return False
    
    if not os.path.exists(python_path):
        logger.error(f"Python을 찾을 수 없습니다: {python_path}")
        return False
    
    # pip 업데이트
    if not update_pip(pip_path):
        logger.warning("pip 업데이트에 실패했습니다. 계속 진행합니다.")
    
    # 패키지 설치
    install_packages(pip_path, python_path)
    
    # 환경 변수 파일 생성
    create_env_file()
    
    # 활성화 스크립트 생성
    create_activation_scripts(venv_dir)
    
    logger.info("환경 설정이 완료되었습니다!")
    logger.info("이제 다음 명령으로 애플리케이션을 실행할 수 있습니다:")
    
    if platform.system() == "Windows":
        logger.info("1. activate_venv.bat 실행 (또는 가상 환경 수동 활성화)")
        logger.info("2. python run.py 명령으로 애플리케이션 실행")
    else:
        logger.info("1. source activate_venv.sh (또는 가상 환경 수동 활성화)")
        logger.info("2. python run.py 명령으로 애플리케이션 실행")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except Exception as e:
        logger.error(f"환경 설정 중 예외가 발생했습니다: {str(e)}")
        sys.exit(1) 