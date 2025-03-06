#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
국책과제 Expert AI 가상환경 설정 스크립트
이 스크립트는 프로젝트에 필요한 가상환경을 설정하고 필요한 패키지를 설치합니다.
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('setup_venv')

def create_venv():
    """가상환경을 생성합니다."""
    venv_path = Path('.venv')
    
    if venv_path.exists():
        logger.info("가상환경이 이미 존재합니다.")
        return True
    
    try:
        logger.info("가상환경 생성 중...")
        subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
        logger.info("가상환경이 성공적으로 생성되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"가상환경 생성 중 오류가 발생했습니다: {e}")
        return False

def install_requirements():
    """requirements.txt 파일에서 필요한 패키지를 설치합니다."""
    requirements_path = Path('requirements.txt')
    
    if not requirements_path.exists():
        logger.error("requirements.txt 파일을 찾을 수 없습니다.")
        return False
    
    # 운영체제에 따라 가상환경의 Python 및 pip 경로 설정
    if platform.system() == 'Windows':
        python_path = '.venv\\Scripts\\python.exe'
        pip_path = '.venv\\Scripts\\pip.exe'
    else:
        python_path = '.venv/bin/python'
        pip_path = '.venv/bin/pip'
    
    try:
        logger.info("pip 업그레이드 중...")
        subprocess.run([pip_path, 'install', '--upgrade', 'pip'], check=True)
        
        logger.info("필수 패키지 설치 중...")
        subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
        
        logger.info("패키지가 성공적으로 설치되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"패키지 설치 중 오류가 발생했습니다: {e}")
        return False

def create_directories():
    """필요한 디렉토리를 생성합니다."""
    directories = ['temp', 'output', 'logs']
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.info(f"'{directory}' 디렉토리 생성 중...")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("필요한 디렉토리가 생성되었습니다.")
    return True

def main():
    """메인 함수"""
    logger.info("국책과제 Expert AI 가상환경 설정을 시작합니다.")
    
    # 가상환경 생성
    if not create_venv():
        logger.error("가상환경 설정에 실패했습니다.")
        return False
    
    # 필요한 패키지 설치
    if not install_requirements():
        logger.error("패키지 설치에 실패했습니다.")
        return False
    
    # 필요한 디렉토리 생성
    if not create_directories():
        logger.error("디렉토리 생성에 실패했습니다.")
        return False
    
    logger.info("가상환경 설정이 완료되었습니다.")
    logger.info("가상환경을 활성화하려면 다음 명령을 실행하세요:")
    
    if platform.system() == 'Windows':
        logger.info(".venv\\Scripts\\activate")
    else:
        logger.info("source .venv/bin/activate")
    
    return True

if __name__ == "__main__":
    main() 