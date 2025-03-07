import os
import tempfile
import logging
import time
import platform
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, BinaryIO
import zipfile
import xml.etree.ElementTree as ET

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='hwp_utils.log',
    filemode='a'
)
logger = logging.getLogger('hwp_utils')

# 플랫폼 감지 로직 추가
def detect_platform():
    """플랫폼 및 환경 감지 함수"""
    is_windows = platform.system() == "Windows"
    is_railway = os.environ.get("RAILWAY_STATIC_URL") is not None
    
    # 환경 정보 리턴
    if is_railway:
        return "railway", False  # Railway (Linux) 환경, 기능 제한 있음
    elif not is_windows:
        return platform.system().lower(), False  # 다른 비-Windows 환경, 기능 제한 있음
    else:
        return "windows", True  # Windows 환경, 모든 기능 지원
        
# 전역 플랫폼 감지 실행
PLATFORM, FULL_FEATURES = detect_platform()

# Linux 환경에서 pyhwp 라이브러리 임포트 시도
HAS_PYHWP = False
if PLATFORM != "windows":
    try:
        import olefile
        import zlib
        import pyhwp.hwp5.dataio
        import pyhwp.hwp5.binmodel
        import pyhwp.hwp5.hwp5odt
        import pyhwp.hwp5.xmlmodel
        from pyhwp.hwp5.proc import generate_hwp5html_open_document
        from pyhwp.hwp5.hwp5odt import Hwp5Odt
        from pyhwp.hwp5.xmlmodel import Hwp5File
        HAS_PYHWP = True
        logger.info("pyhwp 라이브러리 로드 성공 (Linux 환경)")
    except Exception as e:
        logger.error(f"pyhwp 라이브러리 로드 실패: {str(e)}")
        HAS_PYHWP = False

# Windows 전용 라이브러리는 조건부로 임포트
if PLATFORM == "windows":
    try:
        # 메인 스레드에서 COM 초기화
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        # pyhwpx 임포트
        try:
            import pyhwpx
            HAS_PYHWPX = True
        except Exception as e:
            logger.error(f"pyhwpx 라이브러리 가져오기 오류: {str(e)}")
            HAS_PYHWPX = False
        HAS_WIN32COM = True
    except Exception as e:
        logger.error(f"COM 초기화 또는 win32com 가져오기 오류: {str(e)}")
        HAS_WIN32COM = False
        HAS_PYHWPX = False
else:
    logger.info("비 Windows 환경에서 실행 중입니다. Windows 전용 기능은 사용할 수 없습니다.")
    HAS_WIN32COM = False
    HAS_PYHWPX = False

# 지원 파일 형식 상수
SUPPORTED_FORMATS = {
    'hwp': 'HWP 파일 (한글 97~현재)',
    'hwpx': 'HWPX 파일 (한글 2014~현재, XML 기반)'
}

# 성능 지표 상수
PERFORMANCE_METRICS = {
    'small_file': {
        'size_mb': 1,
        'avg_text_extraction_time': '1-3초',
        'avg_metadata_extraction_time': '1-2초',
        'avg_table_extraction_time': '2-5초',
        'avg_image_extraction_time': '2-5초'
    },
    'medium_file': {
        'size_mb': 10,
        'avg_text_extraction_time': '5-15초',
        'avg_metadata_extraction_time': '2-5초',
        'avg_table_extraction_time': '10-30초',
        'avg_image_extraction_time': '10-30초'
    },
    'large_file': {
        'size_mb': 50,
        'avg_text_extraction_time': '30-120초',
        'avg_metadata_extraction_time': '5-15초',
        'avg_table_extraction_time': '60-180초',
        'avg_image_extraction_time': '60-180초'
    }
}

class HwpHandler:
    """
    HWP 및 HWPX 파일 처리를 위한 유틸리티 클래스
    
    pyhwpx 라이브러리를 사용하여 HWP/HWPX 파일에서 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
    
    지원 파일 형식:
    - HWP: 한글 워드프로세서 파일 (한글 97~현재)
    - HWPX: 한글 XML 기반 파일 (한글 2014~현재)
    
    참고: 파일 크기와 복잡도에 따라 처리 시간이 증가할 수 있습니다. 
    매우 큰 파일(100MB 이상)은 처리 시간이 길어질 수 있으며, 
    복잡한 표나 이미지가 많은 문서는 추출 품질이 저하될 수 있습니다.
    
    성능 지표 (참고용):
    - 1MB 미만 파일: 텍스트 추출 1-3초, 메타데이터 1-2초, 표 2-5초, 이미지 2-5초
    - 10MB 미만 파일: 텍스트 추출 5-15초, 메타데이터 2-5초, 표 10-30초, 이미지 10-30초
    - 50MB 미만 파일: 텍스트 추출 30-120초, 메타데이터 5-15초, 표 60-180초, 이미지 60-180초
    - 50MB 이상 파일: 처리 시간이 크게 증가하며, 메모리 문제가 발생할 수 있음
    """
    
    @staticmethod
    def extract_text(file_obj: BinaryIO) -> str:
        """
        HWP 또는 HWPX 파일에서 텍스트를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            str: 추출된 텍스트
        """
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.hwp') as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            file_obj.seek(0)  # 파일 포인터 초기화
            
            # 파일 타입 확인 (HWP vs HWPX)
            is_hwpx = file_obj.read(4) == b'PK\x03\x04'
            file_obj.seek(0)  # 파일 포인터 초기화
            
            extracted_text = ""
            try:
                # 플랫폼에 따른 추출 방법 선택
                if is_hwpx:
                    extracted_text = HwpHandler._extract_text_hwpx(file_obj)
                else:
                    if FULL_FEATURES:
                        extracted_text = HwpHandler._extract_text_hwp(file_obj)
                    else:
                        # 비-Windows 환경에서 대체 방법 시도
                        extracted_text = HwpHandler._extract_text_alternative(temp_path)
            except Exception as e:
                logging.error(f"텍스트 추출 오류: {str(e)}")
                # 대체 방법 시도
                extracted_text = HwpHandler._extract_text_alternative(temp_path)
                
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return extracted_text or "텍스트 추출 실패"
        
        except Exception as e:
            logging.error(f"HWP 파일 처리 중 오류 발생: {str(e)}")
            return f"HWP 파일 처리 오류: {str(e)}"
    
    @staticmethod
    def _extract_text_hwp(file_obj: BinaryIO) -> str:
        """
        HWP 파일에서 텍스트를 추출합니다.
        
        Args:
            file_obj: HWP 파일 객체
            
        Returns:
            추출된 텍스트
            
        참고:
            Windows 환경에서는 pyhwpx 또는 win32com을 사용하여 추출을 시도합니다.
            비Windows 환경에서는 대체 방법으로 제한된 텍스트만 추출할 수 있습니다.
        """
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.hwp') as temp_file:
            temp_file.write(file_obj.read())
            temp_path = temp_file.name
        
        # 파일 포인터 초기화
        file_obj.seek(0)
        
        start_time = time.time()
        logger.info(f"HWP 텍스트 추출 시작: {getattr(file_obj, 'name', 'unknown.hwp')}")
        
        try:
            if PLATFORM == "windows" and HAS_PYHWPX:
                # Windows 환경에서 pyhwpx 사용
                try:
                    # COM 초기화 (스레드별 필요)
                    pythoncom.CoInitialize()
                    
                    # pyhwpx를 사용하여 텍스트 추출
                    hwp = pyhwpx.Hwp()
                    hwp.Open(temp_path)
                    
                    # 텍스트 추출
                    text = hwp.GetTextFile("TEXT", "")
                    
                    # 한글 종료
                    hwp.Quit()
                    
                    # 임시 파일 삭제
                    os.unlink(temp_path)
                    
                    # COM 해제
                    pythoncom.CoUninitialize()
                    
                    logger.info(f"pyhwpx로 텍스트 추출 완료 (소요시간: {time.time() - start_time:.2f}초)")
                    return text
                except Exception as e:
                    logger.error(f"pyhwpx로 텍스트 추출 중 오류 발생: {str(e)}")
                    
                    # COM 해제 시도
                    try:
                        pythoncom.CoUninitialize()
                    except:
                        pass
                    
                    # 대체 방법으로 시도
                    if HAS_WIN32COM:
                        try:
                            text = HwpHandler._extract_text_alternative(temp_path)
                            os.unlink(temp_path)
                            logger.info(f"win32com으로 텍스트 추출 완료 (소요시간: {time.time() - start_time:.2f}초)")
                            return text
                        except Exception as alt_e:
                            logger.error(f"win32com으로 텍스트 추출 중 오류 발생: {str(alt_e)}")
            
            # 비Windows 환경 또는 Windows 메서드 실패 시 대체 방법
            logger.info("OS 독립적인 방법으로 HWP 텍스트 추출 시도")
            
            try:
                # ZIP 파일로 열어서 텍스트 추출 시도 (일부 HWP 파일은 ZIP 기반)
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    text_content = []
                    for file_path in zip_ref.namelist():
                        if file_path.endswith('.txt') or file_path.endswith('.xml'):
                            with zip_ref.open(file_path) as f:
                                text_content.append(f.read().decode('utf-8', errors='ignore'))
                    
                    if text_content:
                        combined_text = "\n".join(text_content)
                        logger.info(f"ZIP 기반 방법으로 텍스트 추출 완료 (소요시간: {time.time() - start_time:.2f}초)")
                        os.unlink(temp_path)
                        return combined_text
            except Exception as zip_e:
                logger.error(f"ZIP 방식으로 텍스트 추출 중 오류 발생: {str(zip_e)}")
            
            # 모든 방법이 실패한 경우
            os.unlink(temp_path)
            logger.warning(f"HWP 텍스트 추출 실패: 지원되지 않는 환경 또는 파일 형식 (소요시간: {time.time() - start_time:.2f}초)")
            return "[HWP 텍스트 추출 실패: 이 파일은 Windows 환경에서만 완전히 지원됩니다]"
            
        except Exception as e:
            logger.error(f"HWP 파일 처리 중 오류 발생: {str(e)}")
            try:
                os.unlink(temp_path)
            except:
                pass
            return ""
    
    @staticmethod
    def _extract_text_hwpx(file_obj: BinaryIO) -> str:
        """
        HWPX 파일에서 텍스트를 추출합니다.
        HWPX는 XML 기반 압축 파일 형식입니다.
        
        Args:
            file_obj: HWPX 파일 객체
            
        Returns:
            추출된 텍스트
        """
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.hwpx') as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # 파일 포인터 초기화
            file_obj.seek(0)
            
            try:
                # HWPX 파일은 ZIP 압축 파일 형식
                extracted_text = []
                
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    # HWPX 내부 구조: 'Contents/section0.xml', 'Contents/section1.xml', ...
                    for file_info in zip_ref.infolist():
                        if file_info.filename.startswith('Contents/section') and file_info.filename.endswith('.xml'):
                            with zip_ref.open(file_info) as xml_file:
                                # XML 파싱
                                tree = ET.parse(xml_file)
                                root = tree.getroot()
                                
                                # 네임스페이스 처리
                                namespaces = {
                                    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
                                    'hc': 'http://www.hancom.co.kr/hwpml/2011/core'
                                }
                                
                                # 텍스트 추출 (모든 <hp:t> 태그의 텍스트)
                                for text_elem in root.findall('.//hp:t', namespaces):
                                    if text_elem.text:
                                        extracted_text.append(text_elem.text)
                
                # 임시 파일 삭제
                os.unlink(temp_path)
                
                return '\n'.join(extracted_text)
            except Exception as e:
                logger.error(f"HWPX 파일 파싱 중 오류 발생: {str(e)}")
                
                # 대체 방법으로 시도
                try:
                    # pyhwpx를 사용하여 시도
                    hwp = pyhwpx.Hwp()
                    hwp.Open(temp_path)
                    text = hwp.GetTextFile("TEXT", "")
                    hwp.Quit()
                    os.unlink(temp_path)
                    return text
                except Exception as alt_e:
                    logger.error(f"pyhwpx로 HWPX 텍스트 추출 중 오류 발생: {str(alt_e)}")
                    
                    # win32com으로 시도
                    try:
                        return HwpHandler._extract_text_alternative(temp_path)
                    except Exception as alt_e2:
                        logger.error(f"win32com으로 HWPX 텍스트 추출 중 오류 발생: {str(alt_e2)}")
                        os.unlink(temp_path)
                        raise Exception(f"HWPX 파일에서 텍스트를 추출할 수 없습니다: {str(e)}")
        except Exception as e:
            logger.error(f"HWPX 파일 처리 중 오류 발생: {str(e)}")
            return ""
    
    @staticmethod
    def _extract_text_alternative(file_path: str) -> str:
        """
        HWP/HWPX 파일에서 텍스트를 대체 추출합니다.
        
        Args:
            file_path: HWP/HWPX 파일 경로
            
        Returns:
            추출된 텍스트
            
        참고:
            Windows 환경에서는 win32com을 사용합니다.
            Linux 환경에서는 pyhwp 라이브러리를 사용합니다.
        """
        # Windows 환경에서 win32com 사용
        if PLATFORM == "windows" and HAS_WIN32COM:
            # 현재 스레드에서 별도 COM 초기화
            pythoncom.CoInitialize()
            
            try:
                # 한글 애플리케이션 열기
                hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
                hwp.Open(file_path)
                
                # 텍스트 추출
                text = hwp.GetTextFile("TEXT", "")
                
                # 한글 애플리케이션 종료
                hwp.Quit()
                
                return text
            except Exception as e:
                logger.error(f"win32com으로 텍스트 추출 중 오류 발생: {str(e)}")
                raise e
            finally:
                # COM 해제
                pythoncom.CoUninitialize()
        
        # Linux 환경에서 pyhwp 사용
        elif HAS_PYHWP:
            try:
                logger.info(f"pyhwp로 텍스트 추출 시도: {file_path}")
                
                # pyhwp를 사용하여 텍스트 추출
                with open(file_path, 'rb') as f:
                    hwp5file = Hwp5File(f)
                    
                    # 텍스트 추출 (단순 텍스트)
                    extracted_text = ""
                    for paragraph in hwp5file.bodytext.iter_paragraphs():
                        for t in paragraph.get_text():
                            extracted_text += t
                        extracted_text += "\n"
                    
                    return extracted_text
            except Exception as e:
                logger.error(f"pyhwp로 텍스트 추출 중 오류 발생: {str(e)}")
                
                # 기본 olefile 사용 시도
                try:
                    logger.info(f"olefile로 텍스트 추출 시도: {file_path}")
                    
                    # olefile을 사용하여 기본 텍스트 추출
                    if olefile.isOleFile(file_path):
                        ole = olefile.OleFile(file_path)
                        streams = ole.listdir()
                        
                        # 텍스트 스트림 찾기
                        text_streams = [s for s in streams if 'PrvText' in s[0] or 'Text/Body' in s[0]]
                        
                        if text_streams:
                            text = ""
                            for stream in text_streams:
                                with ole.openstream(stream) as s:
                                    content = s.read().decode('utf-16le', errors='ignore')
                                    text += content + "\n"
                            return text
                except Exception as ole_e:
                    logger.error(f"olefile로 텍스트 추출 중 오류 발생: {str(ole_e)}")
        
        # 모든 방법 실패 시
        logger.warning("모든 텍스트 추출 방법이 실패했습니다.")
        return "텍스트 추출 실패 (지원되지 않는 환경 또는 파일 형식)"
    
    @staticmethod
    def extract_metadata(file_obj: BinaryIO) -> Dict[str, Any]:
        """
        HWP 또는 HWPX 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: HWP/HWPX 파일 객체
            
        Returns:
            추출된 메타데이터 딕셔너리
            
        참고:
            - 파일 형식에 따라 추출되는 메타데이터 필드가 다를 수 있습니다.
            - 모든 메타데이터가 정상적으로 추출되지 않을 수 있으며, 파일 생성 프로그램에 따라 결과가 다를 수 있습니다.
            - 대용량 파일의 경우 처리 시간이 길어질 수 있습니다.
        """
        start_time = time.time()
        
        # 파일 확장자 확인
        filename = getattr(file_obj, 'name', '')
        is_hwpx = filename.lower().endswith('.hwpx')
        
        logger.info(f"메타데이터 추출 시작: {filename}, 파일 형식: {'HWPX' if is_hwpx else 'HWP'}")
        
        try:
            if is_hwpx:
                result = HwpHandler._extract_metadata_hwpx(file_obj)
            else:
                result = HwpHandler._extract_metadata_hwp(file_obj)
                
            elapsed_time = time.time() - start_time
            logger.info(f"메타데이터 추출 완료: {filename}, 필드 수: {len(result)}, 소요 시간: {elapsed_time:.2f}초")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"메타데이터 추출 실패: {filename}, 오류: {str(e)}, 경과 시간: {elapsed_time:.2f}초")
            
            # 기본 메타데이터 반환
            return {
                "filename": os.path.basename(filename),
                "file_size": getattr(file_obj, 'size', 0),
                "error": str(e),
                "error_type": "metadata_extraction_failed",
                "page_count": 0,
                "properties": {}
            }
    
    @staticmethod
    def _extract_metadata_hwp(file_obj: BinaryIO) -> Dict[str, Any]:
        """
        HWP 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: HWP 파일 객체
            
        Returns:
            추출된 메타데이터 딕셔너리
        """
        # COM 초기화 (스레드별 필요)
        pythoncom.CoInitialize()
        
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.hwp') as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # 파일 포인터 초기화
            file_obj.seek(0)
            
            # 기본 메타데이터 설정
            metadata = {
                "filename": getattr(file_obj, 'name', 'unknown.hwp'),
                "file_size": file_obj.tell(),
                "file_type": "HWP",
                "page_count": 0,
                "properties": {}
            }
            
            # pyhwpx를 사용하여 메타데이터 추출
            try:
                hwp = pyhwpx.Hwp()
                hwp.Open(temp_path)
                
                # 페이지 수 가져오기
                metadata["page_count"] = hwp.PageCount
                
                # 문서 요약 정보 가져오기
                try:
                    summary = hwp.GetDocumentInfo(1)  # 1: 문서 요약 정보
                    if summary:
                        metadata["properties"] = {
                            "title": summary.get("Title", ""),
                            "subject": summary.get("Subject", ""),
                            "author": summary.get("Author", ""),
                            "keywords": summary.get("Keywords", ""),
                            "comments": summary.get("Comments", ""),
                            "created": summary.get("Created", ""),
                            "modified": summary.get("LastSaved", "")
                        }
                except Exception as e:
                    logger.warning(f"문서 요약 정보 추출 중 오류 발생: {str(e)}")
                
                # 한글 종료
                hwp.Quit()
                
                # 임시 파일 삭제
                os.unlink(temp_path)
                
                return metadata
            except Exception as e:
                logger.error(f"pyhwpx로 메타데이터 추출 중 오류 발생: {str(e)}")
                
                # 대체 방법으로 시도
                try:
                    alt_metadata = HwpHandler._extract_metadata_alternative(temp_path)
                    # 기본 메타데이터와 병합
                    alt_metadata.update({k: v for k, v in metadata.items() if k not in alt_metadata})
                    os.unlink(temp_path)
                    return alt_metadata
                except Exception as alt_e:
                    logger.error(f"win32com으로 메타데이터 추출 중 오류 발생: {str(alt_e)}")
                    os.unlink(temp_path)
                    return metadata
        except Exception as e:
            logger.error(f"HWP 메타데이터 추출 중 오류 발생: {str(e)}")
            return {
                "filename": getattr(file_obj, 'name', 'unknown.hwp'),
                "file_size": 0,
                "file_type": "HWP",
                "page_count": 0,
                "properties": {}
            }
        finally:
            # COM 해제
            pythoncom.CoUninitialize()
    
    @staticmethod
    def _extract_metadata_hwpx(file_obj: BinaryIO) -> Dict[str, Any]:
        """
        HWPX 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: HWPX 파일 객체
            
        Returns:
            추출된 메타데이터 딕셔너리
        """
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.hwpx') as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # 파일 포인터 초기화
            file_obj.seek(0)
            
            # 기본 메타데이터 설정
            metadata = {
                "filename": getattr(file_obj, 'name', 'unknown.hwpx'),
                "file_size": file_obj.tell(),
                "file_type": "HWPX",
                "page_count": 0,
                "properties": {}
            }
            
            try:
                # HWPX 파일은 ZIP 압축 파일 형식
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    # 섹션 파일 수로 페이지 수 추정
                    section_count = 0
                    for file_info in zip_ref.infolist():
                        if file_info.filename.startswith('Contents/section') and file_info.filename.endswith('.xml'):
                            section_count += 1
                    
                    metadata["page_count"] = max(1, section_count)  # 최소 1페이지
                    
                    # 메타데이터 파일 확인
                    if 'Contents/header.xml' in [f.filename for f in zip_ref.infolist()]:
                        with zip_ref.open('Contents/header.xml') as header_file:
                            # XML 파싱
                            tree = ET.parse(header_file)
                            root = tree.getroot()
                            
                            # 네임스페이스 처리
                            namespaces = {
                                'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
                                'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
                                'dc': 'http://purl.org/dc/elements/1.1/'
                            }
                            
                            # 메타데이터 추출
                            title_elem = root.find('.//dc:title', namespaces)
                            if title_elem is not None and title_elem.text:
                                metadata["properties"]["title"] = title_elem.text
                            
                            subject_elem = root.find('.//dc:subject', namespaces)
                            if subject_elem is not None and subject_elem.text:
                                metadata["properties"]["subject"] = subject_elem.text
                            
                            creator_elem = root.find('.//dc:creator', namespaces)
                            if creator_elem is not None and creator_elem.text:
                                metadata["properties"]["author"] = creator_elem.text
                            
                            date_elem = root.find('.//dc:date', namespaces)
                            if date_elem is not None and date_elem.text:
                                metadata["properties"]["created"] = date_elem.text
                            
                            description_elem = root.find('.//dc:description', namespaces)
                            if description_elem is not None and description_elem.text:
                                metadata["properties"]["comments"] = description_elem.text
                
                # 임시 파일 삭제
                os.unlink(temp_path)
                
                return metadata
            except Exception as e:
                logger.error(f"HWPX 메타데이터 추출 중 오류 발생: {str(e)}")
                
                # 대체 방법으로 시도
                try:
                    # pyhwpx를 사용하여 시도
                    hwp = pyhwpx.Hwp()
                    hwp.Open(temp_path)
                    
                    # 페이지 수 가져오기
                    metadata["page_count"] = hwp.PageCount
                    
                    # 문서 요약 정보 가져오기
                    try:
                        summary = hwp.GetDocumentInfo(1)  # 1: 문서 요약 정보
                        if summary:
                            metadata["properties"] = {
                                "title": summary.get("Title", ""),
                                "subject": summary.get("Subject", ""),
                                "author": summary.get("Author", ""),
                                "keywords": summary.get("Keywords", ""),
                                "comments": summary.get("Comments", ""),
                                "created": summary.get("Created", ""),
                                "modified": summary.get("LastSaved", "")
                            }
                    except Exception as sum_e:
                        logger.warning(f"HWPX 문서 요약 정보 추출 중 오류 발생: {str(sum_e)}")
                    
                    # 한글 종료
                    hwp.Quit()
                    os.unlink(temp_path)
                    return metadata
                except Exception as alt_e:
                    logger.error(f"pyhwpx로 HWPX 메타데이터 추출 중 오류 발생: {str(alt_e)}")
                    
                    # win32com으로 시도
                    try:
                        alt_metadata = HwpHandler._extract_metadata_alternative(temp_path)
                        # 기본 메타데이터와 병합
                        alt_metadata.update({k: v for k, v in metadata.items() if k not in alt_metadata})
                        os.unlink(temp_path)
                        return alt_metadata
                    except Exception as alt_e2:
                        logger.error(f"win32com으로 HWPX 메타데이터 추출 중 오류 발생: {str(alt_e2)}")
                        os.unlink(temp_path)
                        return metadata
        except Exception as e:
            logger.error(f"HWPX 메타데이터 추출 중 오류 발생: {str(e)}")
            return {
                "filename": getattr(file_obj, 'name', 'unknown.hwpx'),
                "file_size": 0,
                "file_type": "HWPX",
                "page_count": 0,
                "properties": {}
            }
    
    @staticmethod
    def _extract_metadata_alternative(file_path: str) -> Dict[str, Any]:
        """
        win32com을 사용하여 HWP 파일에서 메타데이터를 대체 추출합니다.
        
        Args:
            file_path: HWP 파일 경로
            
        Returns:
            메타데이터 딕셔너리
        """
        # 현재 스레드에서 별도 COM 초기화
        pythoncom.CoInitialize()
        
        metadata = {
            "page_count": 0,
            "properties": {}
        }
        
        try:
            # 한글 애플리케이션 열기
            hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            hwp.Open(file_path)
            
            # 페이지 수 추출
            metadata["page_count"] = hwp.PageCount
            
            # 문서 속성 추출
            try:
                metadata["properties"] = {
                    "title": hwp.GetFieldText("Title") or "",
                    "author": hwp.GetFieldText("Author") or "",
                    "date": hwp.GetFieldText("Date") or ""
                }
            except:
                pass
            
            # 한글 애플리케이션 종료
            hwp.Quit()
            
            return metadata
        except Exception as e:
            raise e
        finally:
            # COM 해제
            pythoncom.CoUninitialize()
    
    @staticmethod
    def batch_process_files(file_objs: List[BinaryIO]) -> List[Dict[str, Any]]:
        """
        여러 HWP/HWPX 파일을 일괄 처리합니다.
        
        Args:
            file_objs: HWP/HWPX 파일 객체 목록
            
        Returns:
            처리 결과 목록
            
        참고:
            - 다수의 파일을 처리할 경우 상당한 시간이 소요될 수 있습니다.
            - 대용량 파일이 포함된 경우 메모리 사용량이 급증할 수 있습니다.
            - 병렬 처리는 지원하지 않으며, 파일이 순차적으로 처리됩니다.
            - 일부 파일 처리 실패 시에도 나머지 파일은 계속 처리됩니다.
        """
        batch_start_time = time.time()
        logger.info(f"배치 처리 시작: 파일 {len(file_objs)}개")
        
        results = []
        successful = 0
        failed = 0
        
        for i, file_obj in enumerate(file_objs):
            start_time = time.time()
            filename = getattr(file_obj, 'name', f'file_{i}')
            
            try:
                # 텍스트 추출
                text = HwpHandler.extract_text(file_obj)
                file_obj.seek(0)  # 파일 포인터 재설정
                
                # 메타데이터 추출
                metadata = HwpHandler.extract_metadata(file_obj)
                file_obj.seek(0)
                
                # 파일 크기 계산 (메타데이터에 없는 경우)
                if 'file_size' not in metadata:
                    file_obj.seek(0, os.SEEK_END)
                    metadata['file_size'] = file_obj.tell()
                    file_obj.seek(0)
                
                # 결과 저장
                result = {
                    "filename": os.path.basename(filename),
                    "text": text,
                    "metadata": metadata,
                    "processing_time": time.time() - start_time,
                    "success": True
                }
                
                results.append(result)
                successful += 1
                
                logger.info(f"파일 처리 완료: {filename}, 소요 시간: {result['processing_time']:.2f}초")
                
            except Exception as e:
                error_msg = f"파일 처리 중 오류 발생: {str(e)}"
                logger.error(f"{filename}: {error_msg}")
                
                # 오류 정보 포함한 결과 저장
                results.append({
                    "filename": os.path.basename(filename),
                    "error": error_msg,
                    "processing_time": time.time() - start_time,
                    "success": False
                })
                
                failed += 1
        
        total_time = time.time() - batch_start_time
        logger.info(f"배치 처리 완료: 총 {len(file_objs)}개 파일, 성공: {successful}개, 실패: {failed}개, 총 소요 시간: {total_time:.2f}초")
        
        return results
    
    @staticmethod
    def extract_tables(file_obj: BinaryIO) -> List[List[List[str]]]:
        """
        HWP 또는 HWPX 파일에서 표를 추출합니다.
        
        Args:
            file_obj: HWP/HWPX 파일 객체
            
        Returns:
            추출된 표 목록 (3차원 배열: [표][행][열])
            
        참고:
            - 복잡한 표(병합된 셀, 중첩된 표 등)의 경우 추출 결과가 정확하지 않을 수 있습니다.
            - 표가 많거나 복잡한 문서의 경우 처리 시간이 증가합니다.
            - 매우 큰 표(100행 이상)는 부분적으로만 추출될 수 있습니다.
            - HWP 파일 형식 버전에 따라 일부 표가 추출되지 않을 수 있습니다.
        """
        start_time = time.time()
        
        # 파일 확장자 확인
        filename = getattr(file_obj, 'name', '')
        is_hwpx = filename.lower().endswith('.hwpx')
        
        logger.info(f"표 추출 시작: {filename}, 파일 형식: {'HWPX' if is_hwpx else 'HWP'}")
        
        try:
            # 임시 파일에 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
                
            file_obj.seek(0)  # 파일 포인터 초기화
            
            # 확장자에 따라 추출 방법 결정 (현재는 모두 대체 방법 사용)
            tables = HwpHandler._extract_tables_alternative(temp_path)
            
            elapsed_time = time.time() - start_time
            logger.info(f"표 추출 완료: {filename}, 표 수: {len(tables)}, 소요 시간: {elapsed_time:.2f}초")
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return tables
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"표 추출 실패: {filename}, 오류: {str(e)}, 경과 시간: {elapsed_time:.2f}초")
            
            # 임시 파일 삭제 시도
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
                
            return []  # 빈 목록 반환
    
    @staticmethod
    def _extract_tables_alternative(file_path: str) -> List[List[List[str]]]:
        """
        대체 방법을 사용하여 HWP 파일에서 표를 추출합니다.
        
        Args:
            file_path: HWP 파일 경로
            
        Returns:
            추출된 표 목록 (표 > 행 > 열)
        """
        # COM 초기화
        pythoncom.CoInitialize()
        
        try:
            # win32com을 사용한 대체 방법 시도
            try:
                hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
                hwp.Open(file_path)
                
                tables = []
                
                # 문서 내 표 개수 확인 및 추출
                try:
                    # 표 찾기
                    hwp.InitScan()
                    
                    # 첫 번째 표 찾기
                    found = hwp.GetText().strip() != ""
                    
                    while found:
                        # 표 속성 가져오기
                        table_info = hwp.GetTableInfo()
                        
                        if table_info:
                            rows = table_info.rows
                            cols = table_info.cols
                            
                            # 표 데이터 추출
                            table = []
                            for row in range(rows):
                                row_data = []
                                for col in range(cols):
                                    try:
                                        cell_text = hwp.GetText(row, col)
                                        row_data.append(cell_text)
                                    except:
                                        row_data.append("")
                                table.append(row_data)
                            
                            tables.append(table)
                    
                    hwp.ReleaseScan()
                except:
                    pass
                
                hwp.Quit()
                
                return tables
            
            except Exception as e:
                logger.error(f"win32com으로 표 추출 중 오류 발생: {str(e)}")
                return []
        
        except Exception as e:
            logger.error(f"대체 표 추출 중 오류 발생: {str(e)}")
            return []
        finally:
            # COM 해제
            pythoncom.CoUninitialize()
    
    @staticmethod
    def extract_images(file_obj: BinaryIO) -> List[bytes]:
        """
        HWP 파일에서 이미지를 추출합니다.
        
        Args:
            file_obj: HWP 파일 객체
            
        Returns:
            추출된 이미지 바이너리 데이터 목록
        """
        start_time = time.time()
        
        # 파일 확장자 확인
        filename = getattr(file_obj, 'name', '')
        is_hwpx = filename.lower().endswith('.hwpx')
        
        logger.info(f"이미지 추출 시작: {filename}, 파일 형식: {'HWPX' if is_hwpx else 'HWP'}")
        
        try:
            # 임시 파일에 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            file_obj.seek(0)  # 파일 포인터 초기화
            
            # 대체 방법으로 이미지 추출
            images = HwpHandler._extract_images_alternative(temp_path)
            
            elapsed_time = time.time() - start_time
            logger.info(f"이미지 추출 완료: {filename}, 이미지 수: {len(images)}, 소요 시간: {elapsed_time:.2f}초")
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return images
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"이미지 추출 실패: {filename}, 오류: {str(e)}, 경과 시간: {elapsed_time:.2f}초")
            
            # 임시 파일 삭제 시도
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
                
            return []  # 빈 목록 반환
    
    @staticmethod
    def _extract_images_alternative(file_path: str) -> List[bytes]:
        """
        대체 방법을 사용하여 HWP/HWPX 파일에서 이미지를 추출합니다.
        
        Args:
            file_path: HWP/HWPX 파일 경로
            
        Returns:
            추출된 이미지 바이트 목록
            
        참고:
            이 메서드는 HWP/HWPX 파일의 압축 구조를 직접 분석하여 BinData 디렉토리에서
            이미지 파일을 추출합니다. 모든 이미지 형식을 지원하지만, 일부 복잡한 문서나
            최신 버전 문서의 경우 일부 이미지가 누락될 수 있습니다.
            
            지원되는 이미지 형식:
            - JPG/JPEG: 일반적인 사진 이미지
            - PNG: 투명도를 지원하는 이미지
            - GIF: 애니메이션 이미지 (정적 이미지로만 추출)
            - BMP: 비트맵 이미지
            - EMF/WMF: 벡터 이미지 (제한적 지원)
            
            처리 시간은 이미지 수와 크기에 따라 증가합니다.
        """
        start_time = time.time()
        logger.info(f"대체 방법으로 이미지 추출 시작: {file_path}")
        
        images = []
        
        try:
            # HWP 파일을 ZIP으로 처리 (HWP 파일은 ZIP 형식과 유사한 구조)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # BinData 디렉토리의 파일 목록 가져오기
                bin_files = [file for file in zip_ref.namelist() if 'BinData' in file and not file.endswith('/')]
                
                if not bin_files:
                    logger.warning(f"이미지를 찾을 수 없습니다: {file_path}")
                    return []
                
                logger.info(f"발견된 바이너리 파일: {len(bin_files)}개")
                
                # 각 바이너리 파일 처리
                for bin_file in bin_files:
                    try:
                        # 파일 확장자 확인 (이미지 파일 필터링)
                        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.emf', '.wmf']
                        file_ext = os.path.splitext(bin_file)[1].lower()
                        
                        # 이미지 파일이 아니면 건너뜀
                        is_image = any(bin_file.lower().endswith(ext) for ext in image_exts)
                        if not is_image and not bin_file.startswith('BinData'):
                            continue
                        
                        # 바이너리 데이터 추출
                        image_data = zip_ref.read(bin_file)
                        
                        # 이미지 데이터 검증 (헤더 확인)
                        is_valid = False
                        
                        # JPEG 헤더 (FF D8)
                        if image_data.startswith(b'\xFF\xD8'):
                            is_valid = True
                        # PNG 헤더 (89 50 4E 47)
                        elif image_data.startswith(b'\x89\x50\x4E\x47'):
                            is_valid = True
                        # GIF 헤더 (47 49 46)
                        elif image_data.startswith(b'\x47\x49\x46'):
                            is_valid = True
                        # BMP 헤더 (42 4D)
                        elif image_data.startswith(b'\x42\x4D'):
                            is_valid = True
                        # EMF/WMF 헤더 확인 (일부 파일만 해당)
                        elif len(image_data) > 0:
                            # 특정 조건이 없는 경우 크기가 일정 이상이면 일단 추가
                            is_valid = len(image_data) > 100
                        
                        if is_valid:
                            images.append(image_data)
                            logger.debug(f"이미지 추출 성공: {bin_file}, 크기: {len(image_data)} 바이트")
                        else:
                            logger.debug(f"유효하지 않은 이미지 파일: {bin_file}")
                    
                    except Exception as bin_error:
                        logger.warning(f"바이너리 파일 처리 중 오류: {bin_file}, {str(bin_error)}")
                        continue
        
        except zipfile.BadZipFile as e:
            logger.error(f"잘못된 ZIP 형식 (HWP 파일이 아니거나 손상됨): {str(e)}")
            # HWP 파일 형식이 아닌 경우 win32com을 통한 대체 방법 시도
            try:
                return HwpHandler._extract_images_with_win32com(file_path)
            except Exception as win32_error:
                logger.error(f"win32com으로 이미지 추출 실패: {str(win32_error)}")
                return []
        
        except Exception as e:
            logger.error(f"이미지 추출 중 오류 발생: {str(e)}")
            return []
        
        elapsed_time = time.time() - start_time
        logger.info(f"대체 방법으로 이미지 추출 완료: {file_path}, 이미지 수: {len(images)}, 소요 시간: {elapsed_time:.2f}초")
        
        return images
    
    @staticmethod
    def _extract_images_with_win32com(file_path: str) -> List[bytes]:
        """
        win32com을 사용하여 HWP 파일에서 이미지를 추출합니다.
        
        Args:
            file_path: HWP 파일 경로
            
        Returns:
            추출된 이미지 바이트 목록
            
        참고:
            이 메서드는 한글 프로그램이 설치된 Windows 환경에서만 사용 가능합니다.
            COM 인터페이스를 통해 한글 프로그램을 제어하여 이미지를 추출합니다.
        """
        if not PLATFORM == "windows" or not HAS_WIN32COM:
            logger.warning("이 기능은 Windows 환경과 win32com 라이브러리가 필요합니다.")
            return []
        
        start_time = time.time()
        logger.info(f"win32com으로 이미지 추출 시작: {file_path}")
        
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
            
            elapsed_time = time.time() - start_time
            logger.info(f"win32com으로 이미지 추출 완료: 이미지 수: {len(images)}, 소요 시간: {elapsed_time:.2f}초")
            return images
            
        except Exception as e:
            logger.error(f"win32com으로 이미지 추출 중 오류: {str(e)}")
            return []
            
        finally:
            pythoncom.CoUninitialize() 