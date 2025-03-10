import os
import platform
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, BinaryIO, Union
from pathlib import Path

# 로깅 설정
logger = logging.getLogger(__name__)

class DocumentHandler(ABC):
    """
    문서 처리를 위한 추상 기본 클래스
    
    이 클래스는 다양한 문서 형식(HWP, HWPX, PDF 등)을 처리하기 위한
    공통 인터페이스를 정의합니다.
    """
    
    @abstractmethod
    def extract_text(self, file_obj: BinaryIO) -> str:
        """
        문서에서 텍스트를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            str: 추출된 텍스트
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """
        문서에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        pass
    
    @abstractmethod
    def extract_tables(self, file_obj: BinaryIO) -> List[List[List[str]]]:
        """
        문서에서 표를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        pass
    
    @abstractmethod
    def extract_images(self, file_obj: BinaryIO) -> List[bytes]:
        """
        문서에서 이미지를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        pass
    
    @abstractmethod
    def process_document(self, file_obj: BinaryIO, **kwargs) -> Dict[str, Any]:
        """
        문서를 처리하여 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            **kwargs: 추가 매개변수
            
        Returns:
            Dict[str, Any]: 추출된 정보를 담은 딕셔너리
        """
        pass


class DocumentProcessorFactory:
    """
    문서 처리기를 생성하는 팩토리 클래스
    
    이 클래스는 파일 형식과 플랫폼에 따라 적절한 문서 처리기를 생성합니다.
    """
    
    @staticmethod
    def create_handler(file_path: str = None, file_obj: BinaryIO = None, 
                      file_type: str = None, api_keys: Dict[str, str] = None) -> DocumentHandler:
        """
        파일 유형에 맞는 문서 처리기를 생성합니다.
        
        Args:
            file_path: 문서 파일 경로
            file_obj: 이진 파일 객체 (파일 경로 대신 사용 가능)
            file_type: 문서 파일 유형 (자동 감지하지 않을 경우)
            api_keys: API 키 딕셔너리
            
        Returns:
            DocumentHandler: 문서 유형에 맞는 처리기
        """
        # API 키 딕셔너리 초기화
        if api_keys is None:
            api_keys = {}
            
        try:
            # 파일 유형이 명시적으로 제공되지 않은 경우 파일 확장자로 추측
            if file_type is None and file_path is not None:
                file_ext = os.path.splitext(file_path)[1].lower()
                
                if file_ext == '.hwp':
                    file_type = 'hwp'
                elif file_ext == '.hwpx':
                    file_type = 'hwpx'
                elif file_ext == '.pdf':
                    file_type = 'pdf'
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    file_type = 'image'
                else:
                    raise ValueError(f"지원되지 않는 파일 형식입니다: {file_ext}")
            
            # 파일 유형에 따라 적절한 핸들러 반환
            if file_type == 'hwp':
                # Windows 환경에서는 네이티브 핸들러 사용 시도
                if platform.system() == 'Windows':
                    try:
                        from hwp_native_handler import HwpNativeHandler
                        handler = HwpNativeHandler()
                        logger.info("Windows 네이티브 HWP 핸들러를 사용합니다.")
                        return handler
                    except (ImportError, Exception) as e:
                        logger.warning(f"Windows 네이티브 HWP 핸들러를 로드할 수 없습니다: {str(e)}")
                        logger.info("대체 HWP 핸들러로 전환합니다.")
                
                # 대체 HWP 핸들러 (모든 플랫폼에서 작동)
                try:
                    from hwp_handler import HwpHandler
                    handler = HwpHandler()
                    logger.info("기본 HWP 핸들러를 사용합니다.")
                    return handler
                except Exception as e:
                    logger.error(f"HWP 핸들러 초기화 중 오류 발생: {str(e)}")
                    raise RuntimeError(f"HWP 파일을 처리할 수 없습니다: {str(e)}")
            
            # 플랫폼 감지
            system = platform.system()
            
            # 환경 변수에서 플랫폼 설정 가져오기 (Streamlit Cloud에서 설정)
            platform_env_var = os.environ.get("PLATFORM", "").lower()
            hwp_feature_limited_var = os.environ.get("HWP_FEATURE_LIMITED", "").lower()
            
            # 환경 변수 기반 플랫폼 제한 설정
            platform_features_limited = False
            if platform_env_var == "linux" or hwp_feature_limited_var == "true":
                platform_features_limited = True
            
            # PDF 파일인 경우
            if file_type == "pdf":
                # Mistral OCR 핸들러 사용
                from mistral_ocr_handler import MistralOcrHandler
                return MistralOcrHandler(api_key=api_keys.get("MISTRAL_API_KEY", ""))
            
            # HWP/HWPX 파일인 경우
            if file_type in ["hwp", "hwpx"]:
                # Windows 환경에서는 네이티브 핸들러 시도 (플랫폼 제한이 없는 경우)
                if system == "Windows" and not platform_features_limited:
                    try:
                        # HWP 파일
                        if file_type == "hwp":
                            try:
                                import win32com.client
                                from hwp_native_handler import HwpNativeHandler
                                return HwpNativeHandler()
                            except ImportError:
                                logger.warning("win32com을 불러올 수 없습니다. Mistral OCR로 대체합니다.")
                        
                        # HWPX 파일
                        elif file_type == "hwpx":
                            try:
                                import pyhwpx
                                from hwpx_native_handler import HwpxNativeHandler
                                return HwpxNativeHandler()
                            except ImportError:
                                logger.warning("pyhwpx를 불러올 수 없습니다. Mistral OCR로 대체합니다.")
                    except Exception as e:
                        logger.warning(f"네이티브 핸들러 생성 중 오류 발생: {str(e)}")
                
                # Windows가 아니거나 네이티브 라이브러리를 불러올 수 없는 경우
                # Mistral OCR 핸들러 사용
                from mistral_ocr_handler import MistralOcrHandler
                return MistralOcrHandler(api_key=api_keys.get("MISTRAL_API_KEY", ""))
            
            # 기타 파일 형식 또는 알 수 없는 형식
            # 기본적으로 Mistral OCR 핸들러 사용
            from mistral_ocr_handler import MistralOcrHandler
            return MistralOcrHandler(api_key=api_keys.get("MISTRAL_API_KEY", ""))
        except Exception as e:
            logger.error(f"문서 처리기 생성 중 오류 발생: {str(e)}")
            raise RuntimeError(f"문서 처리기를 생성할 수 없습니다: {str(e)}")
    
    @staticmethod
    def get_handler_for_api(file_type: str, api_keys: Dict[str, str]) -> DocumentHandler:
        """
        API 환경에 최적화된 문서 처리기를 생성합니다.
        
        Args:
            file_type: 파일 형식
            api_keys: API 키 딕셔너리
            
        Returns:
            DocumentHandler: 적절한 문서 처리기 인스턴스
        """
        # API 환경에서는 항상 Mistral OCR 핸들러 사용
        from mistral_ocr_handler import MistralOcrHandler
        return MistralOcrHandler(api_key=api_keys.get("MISTRAL_API_KEY", "")) 