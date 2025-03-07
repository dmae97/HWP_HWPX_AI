import os
import time
import json
import base64
import logging
import requests
import tempfile
from typing import Dict, Any, List, Optional, Tuple, BinaryIO, Union
from pathlib import Path
import hashlib
import platform

from document_handler import DocumentHandler

# 로깅 설정
logger = logging.getLogger(__name__)

class MistralOcrHandler(DocumentHandler):
    """
    Mistral AI OCR API를 사용하여 문서에서 텍스트 및 구조적 정보를 추출하는 클래스
    
    이 클래스는 다양한 문서 형식(PDF, HWP, HWPX 등)에서 텍스트를 추출하고
    플랫폼 독립적인 방식으로 문서 처리 기능을 제공합니다.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.mistral.ai/v1/ocr"):
        """
        MistralOcrHandler 초기화
        
        Args:
            api_key: Mistral AI API 키
            base_url: Mistral AI OCR API 엔드포인트 URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 캐시 디렉토리 생성
        self.cache_dir = Path("cache/mistral_ocr")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_text(self, file_obj: BinaryIO) -> str:
        """
        문서에서 텍스트를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            str: 추출된 텍스트
        """
        result = self.process_document(file_obj)
        return result.get("text", "")
    
    def extract_metadata(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """
        문서에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        result = self.process_document(file_obj)
        return result.get("metadata", {})
    
    def extract_tables(self, file_obj: BinaryIO) -> List[List[List[str]]]:
        """
        문서에서 표를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        result = self.process_document(file_obj)
        return result.get("tables", [])
    
    def extract_images(self, file_obj: BinaryIO) -> List[bytes]:
        """
        문서에서 이미지를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        try:
            # OCR 결과 가져오기
            result = self.process_document(file_obj, include_images=True)
            
            # 이미지 추출 로직
            images = []
            
            # 원본 API 응답에서 이미지 데이터 추출
            if "raw_response" in result and "pages" in result["raw_response"]:
                for page in result["raw_response"]["pages"]:
                    if "images" in page:
                        for image_data in page["images"]:
                            if "binary" in image_data:
                                # Base64 디코딩
                                try:
                                    image_bytes = base64.b64decode(image_data["binary"])
                                    images.append(image_bytes)
                                except Exception as e:
                                    logger.error(f"이미지 디코딩 중 오류 발생: {str(e)}")
            
            return images
        except Exception as e:
            logger.error(f"이미지 추출 중 오류 발생: {str(e)}")
            return []
    
    def process_document(self, file_obj: BinaryIO, **kwargs) -> Dict[str, Any]:
        """
        문서를 처리하여 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            **kwargs: 추가 매개변수
                - include_images (bool): 이미지 포함 여부
                - image_limit (int): 추출할 최대 이미지 수
                - image_min_size (int): 추출할 이미지의 최소 크기(픽셀)
                - pages (List[int]): 처리할 페이지 목록
            
        Returns:
            Dict[str, Any]: 추출된 정보를 담은 딕셔너리
        """
        try:
            # 파일 캐싱 및 중복 추출 방지
            file_hash = self._calculate_file_hash(file_obj)
            
            # 캐시 키 생성 (매개변수 포함)
            cache_key = f"{file_hash}"
            if kwargs.get("include_images"):
                cache_key += "_with_images"
            if kwargs.get("pages"):
                cache_key += f"_pages_{'-'.join(map(str, kwargs.get('pages')))}"
            
            cache_path = self.cache_dir / f"{cache_key}.json"
            
            # 캐시 확인
            if cache_path.exists():
                logger.info(f"캐시된 OCR 결과를 사용합니다: {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            
            # 임시 파일로 저장 (필요시 변환 수행)
            with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_suffix(file_obj)) as temp_file:
                file_obj.seek(0)
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # 파일을 PDF로 변환 (HWP 또는 HWPX인 경우)
            if self._is_hwp_format(temp_path):
                pdf_path = self._convert_hwp_to_pdf(temp_path)
                if pdf_path:
                    temp_path = pdf_path
            
            # OCR 처리 요청
            result = self._process_file(temp_path, **kwargs)
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
            
            # 결과 캐싱
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return result
            
        except Exception as e:
            logger.error(f"OCR 처리 중 오류 발생: {str(e)}")
            return {
                "error": str(e),
                "text": "",
                "metadata": {
                    "page_count": 0,
                    "success": False
                },
                "tables": [],
                "images": []
            }
    
    def _process_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        파일을 OCR 처리합니다.
        
        Args:
            file_path: 처리할 파일 경로
            **kwargs: 추가 매개변수
            
        Returns:
            OCR 처리 결과
        """
        # 파일 인코딩
        with open(file_path, "rb") as f:
            file_content = f.read()
            encoded_content = base64.b64encode(file_content).decode("utf-8")
        
        # API 요청 데이터 준비
        data = {
            "file": encoded_content,
            "options": {
                "extract_tables": True,
                "extract_structure": True,
                "language": "ko"  # 한국어 처리
            }
        }
        
        # 추가 옵션 설정
        if kwargs.get("include_images", False):
            data["options"]["extract_images"] = True
            data["options"]["image_limit"] = kwargs.get("image_limit", 10)
            data["options"]["image_min_size"] = kwargs.get("image_min_size", 100)
        
        # 페이지 범위 설정
        if kwargs.get("pages"):
            data["options"]["pages"] = kwargs.get("pages")
        
        # API 호출
        start_time = time.time()
        logger.info(f"Mistral OCR API 요청 시작: {os.path.basename(file_path)}")
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=data,
            timeout=180  # 대용량 문서 처리를 위한 충분한 타임아웃
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Mistral OCR API 응답 완료: {elapsed_time:.2f}초 소요")
        
        # 응답 처리
        if response.status_code == 200:
            ocr_result = response.json()
            
            # 결과 정제 및 구조화
            extracted_text = self._extract_full_text(ocr_result)
            metadata = self._extract_metadata(ocr_result)
            tables = self._extract_tables(ocr_result)
            
            result = {
                "text": extracted_text,
                "metadata": metadata,
                "tables": tables,
                "raw_response": ocr_result  # 원본 응답 보존 (필요시 추가 처리)
            }
            
            return result
        else:
            error_msg = f"OCR API 오류 ({response.status_code}): {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _extract_full_text(self, ocr_result: Dict[str, Any]) -> str:
        """
        OCR 결과에서 전체 텍스트를 추출합니다.
        
        Args:
            ocr_result: OCR API 응답
            
        Returns:
            추출된 전체 텍스트
        """
        full_text = ""
        
        try:
            # 페이지별 텍스트 추출 및 병합
            if "pages" in ocr_result:
                for page in ocr_result["pages"]:
                    if "content" in page:
                        full_text += page["content"] + "\n\n"
            
            return full_text.strip()
        except Exception as e:
            logger.error(f"텍스트 추출 중 오류 발생: {str(e)}")
            return ""
    
    def _extract_metadata(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        OCR 결과에서 메타데이터를 추출합니다.
        
        Args:
            ocr_result: OCR API 응답
            
        Returns:
            추출된 메타데이터
        """
        metadata = {
            "page_count": 0,
            "success": True,
            "properties": {}
        }
        
        try:
            # 페이지 수 추출
            if "pages" in ocr_result:
                metadata["page_count"] = len(ocr_result["pages"])
            
            # 문서 속성 추출 (있는 경우)
            if "metadata" in ocr_result:
                doc_metadata = ocr_result["metadata"]
                
                # 일반적인 메타데이터 필드 매핑
                field_mapping = {
                    "title": "title",
                    "author": "author",
                    "creator": "creator",
                    "producer": "producer",
                    "creation_date": "creationDate",
                    "modification_date": "modDate"
                }
                
                for meta_key, api_key in field_mapping.items():
                    if api_key in doc_metadata:
                        metadata["properties"][meta_key] = doc_metadata[api_key]
            
            return metadata
        except Exception as e:
            logger.error(f"메타데이터 추출 중 오류 발생: {str(e)}")
            return {
                "page_count": 0,
                "success": False,
                "properties": {}
            }
    
    def _extract_tables(self, ocr_result: Dict[str, Any]) -> List[List[List[str]]]:
        """
        OCR 결과에서 표를 추출합니다.
        
        Args:
            ocr_result: OCR API 응답
            
        Returns:
            추출된 표 목록 (3차원 배열: [표][행][열])
        """
        tables = []
        
        try:
            # 페이지별로 표 추출
            if "pages" in ocr_result:
                for page in ocr_result["pages"]:
                    if "tables" in page and page["tables"]:
                        for table_data in page["tables"]:
                            table = []
                            
                            # 행별로 처리
                            if "cells" in table_data:
                                # 행과 열 크기 결정
                                max_row = 0
                                max_col = 0
                                
                                for cell in table_data["cells"]:
                                    row = cell.get("row", 0)
                                    col = cell.get("column", 0)
                                    max_row = max(max_row, row)
                                    max_col = max(max_col, col)
                                
                                # 표 초기화
                                for _ in range(max_row + 1):
                                    table.append(["" for _ in range(max_col + 1)])
                                
                                # 셀 내용 채우기
                                for cell in table_data["cells"]:
                                    row = cell.get("row", 0)
                                    col = cell.get("column", 0)
                                    content = cell.get("content", "")
                                    
                                    # 병합 셀 처리
                                    row_span = cell.get("rowSpan", 1)
                                    col_span = cell.get("columnSpan", 1)
                                    
                                    for r in range(row, row + row_span):
                                        for c in range(col, col + col_span):
                                            if r < len(table) and c < len(table[0]):
                                                table[r][c] = content
                            
                            if table:
                                tables.append(table)
            
            return tables
        except Exception as e:
            logger.error(f"표 추출 중 오류 발생: {str(e)}")
            return []
    
    def _calculate_file_hash(self, file_obj: BinaryIO) -> str:
        """
        파일의 해시값을 계산합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            파일 해시 문자열
        """
        file_obj.seek(0)
        file_hash = hashlib.md5(file_obj.read()).hexdigest()
        file_obj.seek(0)
        
        return file_hash
    
    def _get_suffix(self, file_obj: BinaryIO) -> str:
        """
        파일 객체에서 확장자를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            파일 확장자
        """
        filename = getattr(file_obj, 'name', '')
        suffix = Path(filename).suffix
        
        if not suffix:
            # 파일 매직 바이트로 추정
            file_obj.seek(0)
            magic_bytes = file_obj.read(4)
            file_obj.seek(0)
            
            if magic_bytes == b'%PDF':
                suffix = '.pdf'
            elif magic_bytes == b'PK\x03\x04':
                suffix = '.hwpx'  # ZIP 기반 형식 (HWPX 가능성)
            else:
                suffix = '.hwp'  # 기본값
        
        return suffix
    
    def _is_hwp_format(self, file_path: str) -> bool:
        """
        파일이 HWP 또는 HWPX 형식인지 확인합니다.
        
        Args:
            file_path: 파일 경로
            
        Returns:
            HWP/HWPX 여부
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in ['.hwp', '.hwpx']
    
    def _convert_hwp_to_pdf(self, hwp_path: str) -> Optional[str]:
        """
        HWP/HWPX 파일을 PDF로 변환합니다.
        
        Args:
            hwp_path: HWP/HWPX 파일 경로
            
        Returns:
            변환된 PDF 파일 경로 또는 None
        """
        try:
            # 플랫폼에 따른 변환 방법 결정
            system = platform.system()
            
            if system == "Windows":
                # Windows 환경에서 변환
                return self._convert_hwp_to_pdf_windows(hwp_path)
            else:
                # 비Windows 환경에서 변환
                return self._convert_hwp_to_pdf_linux(hwp_path)
        except Exception as e:
            logger.error(f"HWP/HWPX를 PDF로 변환 중 오류 발생: {str(e)}")
            return None
    
    def _convert_hwp_to_pdf_windows(self, hwp_path: str) -> Optional[str]:
        """
        Windows 환경에서 HWP/HWPX 파일을 PDF로 변환합니다.
        
        Args:
            hwp_path: HWP/HWPX 파일 경로
            
        Returns:
            변환된 PDF 파일 경로 또는 None
        """
        try:
            import pythoncom
            import win32com.client
            
            # COM 초기화
            pythoncom.CoInitialize()
            
            try:
                # 한글 애플리케이션 생성
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
                
                # 파일 열기
                hwp.Open(hwp_path)
                
                # PDF로 저장
                pdf_path = os.path.splitext(hwp_path)[0] + "_converted.pdf"
                hwp.SaveAs(pdf_path, "PDF")
                
                # 한글 종료
                hwp.Quit()
                
                return pdf_path
            finally:
                # COM 해제
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"Windows에서 HWP/HWPX를 PDF로 변환 중 오류 발생: {str(e)}")
            return None
    
    def _convert_hwp_to_pdf_linux(self, hwp_path: str) -> Optional[str]:
        """
        Linux 환경에서 HWP/HWPX 파일을 PDF로 변환합니다.
        
        Args:
            hwp_path: HWP/HWPX 파일 경로
            
        Returns:
            변환된 PDF 파일 경로 또는 None
        """
        try:
            # unoconv 또는 기타 변환 도구 사용 (설치 필요)
            import subprocess
            
            pdf_path = os.path.splitext(hwp_path)[0] + "_converted.pdf"
            
            # 1. hwp-converter 시도 (hwp-converter 패키지 필요)
            try:
                result = subprocess.run(
                    ["hwp-converter", hwp_path, pdf_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and os.path.exists(pdf_path):
                    return pdf_path
            except FileNotFoundError:
                logger.warning("hwp-converter를 찾을 수 없습니다. 다른 방법을 시도합니다.")
            
            # 2. unoconv 시도 (LibreOffice 기반)
            try:
                result = subprocess.run(
                    ["unoconv", "-f", "pdf", "-o", pdf_path, hwp_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and os.path.exists(pdf_path):
                    return pdf_path
            except FileNotFoundError:
                logger.warning("unoconv를 찾을 수 없습니다. 다른 방법을 시도합니다.")
            
            # 3. LibreOffice 직접 호출 시도
            try:
                result = subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", 
                     os.path.dirname(pdf_path), hwp_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # LibreOffice는 원본 파일명을 유지하므로 이름 변경 필요
                generated_pdf = os.path.splitext(hwp_path)[0] + ".pdf"
                if result.returncode == 0 and os.path.exists(generated_pdf):
                    # 이름 변경
                    os.rename(generated_pdf, pdf_path)
                    return pdf_path
            except FileNotFoundError:
                logger.warning("LibreOffice를 찾을 수 없습니다.")
            
            # 모든 방법 실패
            logger.error("Linux에서 HWP/HWPX를 PDF로 변환하는 모든 방법이 실패했습니다.")
            return None
            
        except Exception as e:
            logger.error(f"Linux에서 HWP/HWPX를 PDF로 변환 중 오류 발생: {str(e)}")
            return None 