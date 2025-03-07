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

class HwpNativeHandler(DocumentHandler):
    """
    Windows 환경에서 HWP 파일을 처리하는 네이티브 핸들러
    
    이 클래스는 win32com을 사용하여 HWP 파일을 처리합니다.
    """
    
    def __init__(self):
        """
        HwpNativeHandler 초기화
        """
        # win32com 라이브러리 가져오기
        try:
            import win32com.client
            import pythoncom
            self.win32com_available = True
        except ImportError:
            logger.warning("win32com을 불러올 수 없습니다. 일부 기능이 제한됩니다.")
            self.win32com_available = False
    
    def extract_text(self, file_obj: BinaryIO) -> str:
        """
        HWP 파일에서 텍스트를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            str: 추출된 텍스트
        """
        result = self.process_document(file_obj)
        return result.get("text", "")
    
    def extract_metadata(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """
        HWP 파일에서 메타데이터를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        result = self.process_document(file_obj)
        return result.get("metadata", {})
    
    def extract_tables(self, file_obj: BinaryIO) -> List[List[List[str]]]:
        """
        HWP 파일에서 표를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        result = self.process_document(file_obj)
        return result.get("tables", [])
    
    def extract_images(self, file_obj: BinaryIO) -> List[bytes]:
        """
        HWP 파일에서 이미지를 추출합니다.
        
        Args:
            file_obj: 이진 파일 객체
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        result = self.process_document(file_obj)
        return result.get("images", [])
    
    def process_document(self, file_obj: BinaryIO, **kwargs) -> Dict[str, Any]:
        """
        HWP 파일을 처리하여 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
        
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
        
        # win32com 사용 가능 여부 확인
        if not self.win32com_available:
            result["error"] = "win32com 라이브러리를 사용할 수 없습니다."
            return result
        
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".hwp") as temp_file:
                file_obj.seek(0)
                temp_file.write(file_obj.read())
                temp_path = temp_file.name
            
            # win32com을 사용하여 HWP 파일 처리
            import win32com.client
            import pythoncom
            
            # COM 초기화
            pythoncom.CoInitialize()
            
            try:
                # 한글 애플리케이션 생성
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
                
                # 파일 열기
                hwp.Open(temp_path)
                
                # 텍스트 추출
                result["text"] = hwp.GetTextFile("TEXT", "")
                
                # 메타데이터 추출
                result["metadata"] = self._extract_metadata_win32com(hwp)
                
                # 표 추출
                result["tables"] = self._extract_tables_win32com(hwp)
                
                # 이미지 추출
                result["images"] = self._extract_images_win32com(hwp, temp_path)
                
                # 한글 종료
                hwp.Quit()
            finally:
                # COM 해제
                pythoncom.CoUninitialize()
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"HWP 파일 처리 중 오류 발생: {str(e)}")
            result["error"] = f"HWP 파일 처리 중 오류가 발생했습니다: {str(e)}"
            return result
    
    def _extract_metadata_win32com(self, hwp) -> Dict[str, Any]:
        """
        win32com을 사용하여 HWP 파일에서 메타데이터를 추출합니다.
        
        Args:
            hwp: HWP 객체
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        metadata = {
            "page_count": 0,
            "properties": {}
        }
        
        try:
            # 페이지 수 추출
            metadata["page_count"] = hwp.PageCount
            
            # 문서 속성 추출
            try:
                metadata["properties"]["title"] = hwp.GetFieldText("문서제목") or ""
            except:
                pass
                
            try:
                metadata["properties"]["author"] = hwp.GetFieldText("작성자") or ""
            except:
                pass
                
            try:
                metadata["properties"]["creation_date"] = hwp.GetFieldText("작성일자") or ""
            except:
                pass
            
            return metadata
        except Exception as e:
            logger.error(f"메타데이터 추출 중 오류 발생: {str(e)}")
            return {
                "page_count": 0,
                "properties": {}
            }
    
    def _extract_tables_win32com(self, hwp) -> List[List[List[str]]]:
        """
        win32com을 사용하여 HWP 파일에서 표를 추출합니다.
        
        Args:
            hwp: HWP 객체
            
        Returns:
            List[List[List[str]]]: 추출된 표 목록 (3차원 배열: [표][행][열])
        """
        tables = []
        
        try:
            # 표 개수 확인
            hwp.InitScan()
            table_count = 0
            
            while True:
                if not hwp.GetText():
                    break
                    
                if hwp.GetCurFieldName() == "TableField":
                    table_count += 1
                    
                    # 표 정보 가져오기
                    hwp.SetPos(hwp.GetPos())
                    hwp.FindCtrl()
                    
                    # 표 선택
                    hwp.SetPos(hwp.GetPos())
                    hwp.SelectCtrl()
                    
                    # 표 내용 가져오기
                    table_text = hwp.GetTextFile("TEXT", "")
                    
                    # 표 내용 파싱
                    rows = table_text.strip().split("\n")
                    table = []
                    
                    for row in rows:
                        cells = row.split("\t")
                        table.append(cells)
                    
                    tables.append(table)
            
            hwp.ReleaseScan()
            
            return tables
        except Exception as e:
            logger.error(f"표 추출 중 오류 발생: {str(e)}")
            return []
    
    def _extract_images_win32com(self, hwp, file_path: str) -> List[bytes]:
        """
        win32com을 사용하여 HWP 파일에서 이미지를 추출합니다.
        
        Args:
            hwp: HWP 객체
            file_path: HWP 파일 경로
            
        Returns:
            List[bytes]: 추출된 이미지 바이트 배열 목록
        """
        images = []
        
        try:
            # 이미지 추출을 위한 임시 디렉토리 생성
            temp_dir = tempfile.mkdtemp()
            
            # 이미지 추출
            hwp.InitScan()
            image_count = 0
            
            while True:
                if not hwp.GetText():
                    break
                    
                if hwp.GetCurFieldName() == "ShapeObject":
                    image_count += 1
                    
                    # 이미지 선택
                    hwp.SetPos(hwp.GetPos())
                    hwp.SelectCtrl()
                    
                    # 이미지 저장
                    image_path = os.path.join(temp_dir, f"image_{image_count}.png")
                    hwp.SavePicture(image_path)
                    
                    # 이미지 읽기
                    if os.path.exists(image_path):
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                            images.append(image_bytes)
                        
                        # 임시 이미지 파일 삭제
                        try:
                            os.unlink(image_path)
                        except:
                            pass
            
            hwp.ReleaseScan()
            
            # 임시 디렉토리 삭제
            try:
                os.rmdir(temp_dir)
            except:
                pass
            
            return images
        except Exception as e:
            logger.error(f"이미지 추출 중 오류 발생: {str(e)}")
            return [] 