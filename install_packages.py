#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
국책과제 Expert AI 패키지 설치 스크립트
이 스크립트는 .venv 가상환경에 필요한 패키지를 설치합니다.
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
logger = logging.getLogger('install_packages')

def install_packages():
    """가상환경에 필요한 패키지를 설치합니다."""
    venv_path = Path('.venv')
    
    if not venv_path.exists():
        logger.error("가상환경이 존재하지 않습니다. 먼저 가상환경을 생성해주세요.")
        return False
    
    # 운영체제에 따라 가상환경의 Python 및 pip 경로 설정
    if platform.system() == 'Windows':
        python_path = '.venv\\Scripts\\python.exe'
        pip_path = '.venv\\Scripts\\pip.exe'
    else:
        python_path = '.venv/bin/python'
        pip_path = '.venv/bin/pip'
    
    try:
        # pip 업그레이드
        logger.info("pip 업그레이드 중...")
        subprocess.run([pip_path, 'install', '--upgrade', 'pip'], check=True)
        
        # 필수 패키지 설치
        logger.info("필수 패키지 설치 중...")
        subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
        
        logger.info("패키지가 성공적으로 설치되었습니다.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"패키지 설치 중 오류가 발생했습니다: {e}")
        return False

if __name__ == "__main__":
    install_packages() 