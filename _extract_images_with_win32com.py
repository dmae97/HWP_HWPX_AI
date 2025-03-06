"""
Windows 환경에서만 사용 가능한 이미지 추출 기능 스텁 파일
"""
import logging
import platform
from typing import List

logger = logging.getLogger('hwp_utils')

IS_WINDOWS = platform.system() == 'Windows'

def extract_images_with_win32com(file_path: str) -> List[bytes]:
    """
    win32com을 사용하여 HWP 파일에서 이미지를 추출하는 스텁 함수
    
    Args:
        file_path: HWP 파일 경로
        
    Returns:
        추출된 이미지 바이트 목록 (비Windows 환경에서는 빈 리스트 반환)
    """
    if not IS_WINDOWS:
        logger.warning("이 기능은 Windows 환경에서만 사용 가능합니다.")
        return []
    
    try:
        # Windows 환경에서만 실제 모듈 임포트
        import pythoncom
        import win32com.client
        
        pythoncom.CoInitialize()
        images = []
        
        try:
            # 한글 애플리케이션 생성
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            
            # 파일 열기
            hwp.Open(file_path)
            
            # 이미지 추출 로직
            # 현재 win32com을 통한 이미지 추출은 복잡하므로 간단한 구현만 제공
            # 실제 구현 시에는 추가 로직 필요
            
            # 이미지 저장 경로 설정
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            try:
                # 이미지 저장 (현재는 단순 파일 저장만 구현)
                # 실제로는 한글 파일 내 이미지를 순회하며 저장하는 로직 필요
                pass
            
            finally:
                # 임시 디렉토리 정리
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 한글 종료
            hwp.Quit()
            
            return images
            
        except Exception as e:
            logger.error(f"win32com으로 이미지 추출 중 오류: {str(e)}")
            return []
            
        finally:
            pythoncom.CoUninitialize()
            
    except ImportError:
        logger.error("win32com 라이브러리를 가져올 수 없습니다. Windows 환경인지 확인하세요.")
        return [] 