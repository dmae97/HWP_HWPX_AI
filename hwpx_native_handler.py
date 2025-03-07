import os
import logging
import tempfile
import base64
import io
from typing import Dict, Any, List, Optional, Tuple, BinaryIO, Union
from pathlib import Path

from document_handler import DocumentHandler

# 로깅 설정
logger = logging.getLogger(__name__)

class HwpxNativeHandler(DocumentHandler):
    """
    Windows 환경에서 HWPX 파일을 처리하는 네이티브 핸들러
    
    이 클래스는 pyhwpx를 사용하여 HWPX 파일을 처리합니다.
    """
    
    def __init__(self):
        """
        HwpxNativeHandler 초기화
        """
        # pyhwpx 라이브러리 가져오기
        try:
            import pyhwpx
            self.pyhwpx_available = True
        except ImportError:
            logger.warning("pyhwpx를 불러올 수 없습니다. 일부 기능이 제한됩니다.")
            self.pyhwpx_available = False
    
    def extract_text(self, file_obj: BinaryIO) -> str:
        """
        HWPX 파일에서 텍스트를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            str: 추출된 텍스트
        """
        result = self.process_document(file_obj)
        return result.get("text", "")
    
    def extract_metadata(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """
        HWPX 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        result = self.process_document(file_obj)
        return result.get("metadata", {})
    
    def extract_tables(self, file_obj: BinaryIO) -> List[List[List[str]]]:
        """
        HWPX 파일에서 표를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        result = self.process_document(file_obj)
        return result.get("tables", [])
    
    def extract_images(self, file_obj: BinaryIO) -> List[bytes]:
        """
        HWPX 파일에서 이미지를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        result = self.process_document(file_obj)
        return result.get("images", [])
    
    def process_document(self, file_obj: BinaryIO, **kwargs) -> Dict[str, Any]:
        """
        HWPX 파일을 처리하여 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            **kwargs: 추가 매개변수
            
        Returns:
            Dict[str, Any]: 추출된 정보를 담은 딕셔너리
        """
        # 결과 초기화
        result = {
            "text": "",
            "metadata": {},
            "tables": [],
            "images": [],
            "error": None
        }
        
        # pyhwpx 사용 가능 여부 확인
        if not self.pyhwpx_available:
            result["error"] = "pyhwpx 라이브러리를 사용할 수 없습니다."
            return result
        
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".hwpx") as temp_file:
                file_obj.seek(0)
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # pyhwpx를 사용하여 HWPX 파일 처리
            import pyhwpx
            
            # 텍스트 추출
            result["text"] = pyhwpx.extract_text(temp_path)
            
            # 메타데이터 추출
            result["metadata"] = self._extract_metadata_pyhwpx(temp_path)
            
            # 표 추출
            result["tables"] = self._extract_tables_pyhwpx(temp_path)
            
            # 이미지 추출
            result["images"] = self._extract_images_pyhwpx(temp_path)
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"HWPX 파일 처리 중 오류 발생: {str(e)}")
            result["error"] = f"HWPX 파일 처리 중 오류가 발생했습니다: {str(e)}"
            return result
    
    def _extract_metadata_pyhwpx(self, file_path: str) -> Dict[str, Any]:
        """
        pyhwpx를 사용하여 HWPX 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_path: HWPX 파일 경로
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        metadata = {
            "page_count": 0,
            "properties": {}
        }
        
        try:
            import pyhwpx
            import zipfile
            import xml.etree.ElementTree as ET
            
            # HWPX 파일은 ZIP 파일 형식
            with zipfile.ZipFile(file_path) as z:
                # 메타데이터 파일 확인
                if "Contents/header.xml" in z.namelist():
                    with z.open("Contents/header.xml") as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        
                        # 네임스페이스 처리
                        namespaces = {
                            "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
                            "hh": "http://www.hancom.co.kr/hwpml/2011/head"
                        }
                        
                        # 문서 정보 추출
                        try:
                            doc_info = root.find(".//hh:docsummary", namespaces)
                            if doc_info is not None:
                                title = doc_info.find("./hh:title", namespaces)
                                if title is not None and title.text:
                                    metadata["properties"]["title"] = title.text
                                
                                author = doc_info.find("./hh:author", namespaces)
                                if author is not None and author.text:
                                    metadata["properties"]["author"] = author.text
                                
                                date = doc_info.find("./hh:date", namespaces)
                                if date is not None and date.text:
                                    metadata["properties"]["creation_date"] = date.text
                        except Exception as e:
                            logger.warning(f"문서 정보 추출 중 오류 발생: {str(e)}")
                
                # 페이지 수 추출 (섹션 수로 대체)
                if "Contents/section0.xml" in z.namelist():
                    section_count = 1
                    while f"Contents/section{section_count}.xml" in z.namelist():
                        section_count += 1
                    
                    metadata["page_count"] = section_count
            
            return metadata
        except Exception as e:
            logger.error(f"메타데이터 추출 중 오류 발생: {str(e)}")
            return {
                "page_count": 0,
                "properties": {}
            }
    
    def _extract_tables_pyhwpx(self, file_path: str) -> List[List[List[str]]]:
        """
        pyhwpx를 사용하여 HWPX 파일에서 표를 추출합니다.
        
        Args:
            file_path: HWPX 파일 경로
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        tables = []
        
        try:
            import pyhwpx
            import zipfile
            import xml.etree.ElementTree as ET
            
            # HWPX 파일은 ZIP 파일 형식
            with zipfile.ZipFile(file_path) as z:
                # 섹션 파일 처리
                section_index = 0
                while f"Contents/section{section_index}.xml" in z.namelist():
                    section_file = f"Contents/section{section_index}.xml"
                    
                    with z.open(section_file) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        
                        # 네임스페이스 처리
                        namespaces = {
                            "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
                            "hc": "http://www.hancom.co.kr/hwpml/2011/content"
                        }
                        
                        # 표 요소 찾기
                        table_elements = root.findall(".//hc:table", namespaces)
                        
                        for table_elem in table_elements:
                            table = []
                            
                            # 행 처리
                            row_elements = table_elem.findall(".//hc:tr", namespaces)
                            for row_elem in row_elements:
                                row = []
                                
                                # 셀 처리
                                cell_elements = row_elem.findall(".//hc:td", namespaces)
                                for cell_elem in cell_elements:
                                    # 셀 내용 추출
                                    cell_text = ""
                                    para_elements = cell_elem.findall(".//hp:p", namespaces)
                                    
                                    for para_elem in para_elements:
                                        text_elements = para_elem.findall(".//hc:t", namespaces)
                                        for text_elem in text_elements:
                                            if text_elem.text:
                                                cell_text += text_elem.text
                                        
                                        # 단락 구분
                                        cell_text += "\n"
                                    
                                    row.append(cell_text.strip())
                                
                                if row:
                                    table.append(row)
                            
                            if table:
                                tables.append(table)
                    
                    section_index += 1
            
            return tables
        except Exception as e:
            logger.error(f"표 추출 중 오류 발생: {str(e)}")
            return []
    
    def _extract_images_pyhwpx(self, file_path: str) -> List[bytes]:
        """
        pyhwpx를 사용하여 HWPX 파일에서 이미지를 추출합니다.
        
        Args:
            file_path: HWPX 파일 경로
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        images = []
        
        try:
            import zipfile
            
            # HWPX 파일은 ZIP 파일 형식
            with zipfile.ZipFile(file_path) as z:
                # 이미지 파일 찾기 (일반적으로 BinData 디렉토리에 저장됨)
                image_files = [f for f in z.namelist() if f.startswith("BinData/")]
                
                for image_file in image_files:
                    # 이미지 확장자 확인
                    if any(image_file.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]):
                        # 이미지 추출
                        with z.open(image_file) as f:
                            image_bytes = f.read()
                            images.append(image_bytes)
            
            return images
        except Exception as e:
            logger.error(f"이미지 추출 중 오류 발생: {str(e)}")
            return [] 