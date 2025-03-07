import os
import platform
import logging
import tempfile
import olefile
import base64
import io
from typing import Dict, Any, List, Optional, Tuple, Union

# 로깅 설정
logger = logging.getLogger(__name__)

def is_hwp_file(file_path: str) -> bool:
    """
    파일이 HWP 파일인지 확인합니다.
    
    Args:
        file_path: 확인할 파일 경로
        
    Returns:
        bool: HWP 파일이면 True, 아니면 False
    """
    try:
        return olefile.isOleFile(file_path)
    except:
        return False

def extract_hwp_text_linux(file_path: str) -> str:
    """
    Linux 환경에서 HWP 파일에서 텍스트를 추출합니다.
    olefile을 사용하여 기본적인 텍스트 추출을 시도합니다.
    
    Args:
        file_path: HWP 파일 경로
        
    Returns:
        str: 추출된 텍스트
    """
    try:
        if not olefile.isOleFile(file_path):
            return "유효한 HWP 파일이 아닙니다."
        
        ole = olefile.OleFile(file_path)
        streams = ole.listdir()
        
        # HWP 파일 내의 텍스트 스트림 찾기
        text_parts = []
        
        # 기본 텍스트 스트림 시도
        text_streams = [s for s in streams if 'PrvText' in s]
        if text_streams:
            for stream in text_streams:
                try:
                    with ole.openstream(stream) as f:
                        data = f.read().decode('utf-16-le', errors='ignore')
                        text_parts.append(data)
                except Exception as e:
                    logger.warning(f"스트림 {stream} 읽기 실패: {str(e)}")
        
        # 다른 텍스트 스트림 시도
        if not text_parts:
            for stream in streams:
                if 'Text' in stream[-1] or 'text' in stream[-1]:
                    try:
                        with ole.openstream(stream) as f:
                            data = f.read().decode('utf-16-le', errors='ignore')
                            text_parts.append(data)
                    except Exception as e:
                        logger.warning(f"스트림 {stream} 읽기 실패: {str(e)}")
        
        ole.close()
        
        if text_parts:
            return "\n\n".join(text_parts)
        else:
            return "텍스트를 추출할 수 없습니다. 이 파일은 Linux 환경에서 제한적으로만 처리할 수 있습니다."
    
    except Exception as e:
        logger.error(f"HWP 텍스트 추출 중 오류 발생: {str(e)}")
        return f"텍스트 추출 중 오류가 발생했습니다: {str(e)}"

def extract_hwp_text_windows(file_path: str) -> str:
    """
    Windows 환경에서 HWP 파일에서 텍스트를 추출합니다.
    pyhwpx 또는 pywin32를 사용하여 텍스트를 추출합니다.
    
    Args:
        file_path: HWP 파일 경로
        
    Returns:
        str: 추출된 텍스트
    """
    try:
        # pyhwpx 사용 시도
        try:
            import pyhwpx
            return pyhwpx.extract_text(file_path)
        except ImportError:
            logger.warning("pyhwpx를 불러올 수 없습니다. pywin32를 사용합니다.")
        
        # pywin32 사용 시도
        try:
            import win32com.client
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            hwp.Open(file_path)
            text = hwp.GetTextFile("TEXT", "")
            hwp.Quit()
            return text
        except Exception as e:
            logger.error(f"pywin32을 사용한 텍스트 추출 실패: {str(e)}")
            return f"텍스트 추출 중 오류가 발생했습니다: {str(e)}"
    
    except Exception as e:
        logger.error(f"HWP 텍스트 추출 중 오류 발생: {str(e)}")
        return f"텍스트 추출 중 오류가 발생했습니다: {str(e)}"

def extract_hwp_text(file_path: str) -> str:
    """
    플랫폼에 따라 적절한 HWP 텍스트 추출 방식을 선택합니다.
    
    Args:
        file_path: HWP 파일 경로
        
    Returns:
        str: 추출된 텍스트
    """
    if platform.system() == "Windows":
        return extract_hwp_text_windows(file_path)
    else:
        return extract_hwp_text_linux(file_path)

def extract_hwpx_text(file_path: str) -> str:
    """
    HWPX 파일에서 텍스트를 추출합니다.
    
    Args:
        file_path: HWPX 파일 경로
        
    Returns:
        str: 추출된 텍스트
    """
    try:
        # Windows 환경에서 pyhwpx 사용 시도
        if platform.system() == "Windows":
            try:
                import pyhwpx
                return pyhwpx.extract_text(file_path)
            except ImportError:
                logger.warning("pyhwpx를 불러올 수 없습니다.")
        
        # 기본 XML 파싱 시도 (HWPX는 ZIP으로 압축된 XML 파일)
        import zipfile
        import xml.etree.ElementTree as ET
        
        if not zipfile.is_zipfile(file_path):
            return "유효한 HWPX 파일이 아닙니다."
        
        text_parts = []
        with zipfile.ZipFile(file_path) as z:
            # HWPX 내부 구조에서 텍스트 포함 XML 파일 찾기
            content_files = [f for f in z.namelist() if f.startswith('Contents/') and f.endswith('.xml')]
            
            for content_file in content_files:
                try:
                    with z.open(content_file) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        
                        # 모든 텍스트 노드 추출
                        for elem in root.iter():
                            if elem.text and elem.text.strip():
                                text_parts.append(elem.text.strip())
                except Exception as e:
                    logger.warning(f"{content_file} 파싱 중 오류: {str(e)}")
        
        if text_parts:
            return "\n".join(text_parts)
        else:
            return "텍스트를 추출할 수 없습니다. 이 파일은 Linux 환경에서 제한적으로만 처리할 수 있습니다."
    
    except Exception as e:
        logger.error(f"HWPX 텍스트 추출 중 오류 발생: {str(e)}")
        return f"텍스트 추출 중 오류가 발생했습니다: {str(e)}"

def process_hwp_file(file_path: str, file_type: str = None) -> Dict[str, Any]:
    """
    HWP 또는 HWPX 파일을 처리하여 텍스트 및 메타데이터를 추출합니다.
    
    Args:
        file_path: 처리할 파일 경로
        file_type: 파일 유형 ('hwp' 또는 'hwpx')
        
    Returns:
        Dict[str, Any]: 추출된 정보를 담은 딕셔너리
    """
    result = {
        "text": "",
        "metadata": {},
        "tables": [],
        "images": [],
        "platform": platform.system(),
        "limited_mode": platform.system() != "Windows"
    }
    
    if file_type is None:
        # 파일 확장자로 유형 추측
        _, ext = os.path.splitext(file_path)
        file_type = ext.lower().replace(".", "")
    
    try:
        # 파일 유형에 따라 적절한 처리 방법 선택
        if file_type == "hwp":
            result["text"] = extract_hwp_text(file_path)
        elif file_type == "hwpx":
            result["text"] = extract_hwpx_text(file_path)
        else:
            result["text"] = "지원되지 않는 파일 형식입니다."
        
        # 메타데이터 추출 시도 (olefile 사용)
        if file_type == "hwp" and olefile.isOleFile(file_path):
            try:
                ole = olefile.OleFile(file_path)
                if ole.exists('\x05HwpSummaryInformation'):
                    with ole.openstream('\x05HwpSummaryInformation') as s:
                        # 메타데이터 추출 로직 (간소화됨)
                        result["metadata"] = {"source": "olefile"}
                ole.close()
            except Exception as e:
                logger.warning(f"메타데이터 추출 실패: {str(e)}")
        
        return result
    
    except Exception as e:
        logger.error(f"파일 처리 중 오류 발생: {str(e)}")
        result["text"] = f"파일 처리 중 오류가 발생했습니다: {str(e)}"
        return result 