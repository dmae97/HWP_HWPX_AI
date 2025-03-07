import os
import logging
import requests
import json
import base64
from typing import Dict, Any, List, Optional, Tuple, Union
import tempfile
from pathlib import Path
import pandas as pd
import uuid

# 로깅 설정
logger = logging.getLogger(__name__)

class PDFHandler:
    """
    Mistral AI OCR API를 활용하여 PDF 문서를 처리하는 클래스
    """
    
    def __init__(self, api_key: str):
        """
        PDFHandler 초기화
        
        Args:
            api_key: Mistral AI API 키
        """
        self.api_key = api_key
        self.api_url = "https://api.mistral.ai/v1/ocr"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def process_pdf(self, file_path: str, include_images: bool = False, 
                   image_limit: int = 10, image_min_size: int = 100,
                   pages: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        PDF 파일을 처리하여 텍스트 및 이미지를 추출합니다.
        
        Args:
            file_path: PDF 파일 경로
            include_images: 이미지 포함 여부
            image_limit: 추출할 최대 이미지 수
            image_min_size: 추출할 이미지의 최소 크기(픽셀)
            pages: 처리할 페이지 목록 (None인 경우 전체 페이지)
            
        Returns:
            Dict[str, Any]: 추출된 정보를 담은 딕셔너리
        """
        result = {
            "text": "",
            "markdown": "",
            "images": [],
            "pages": [],
            "metadata": {
                "page_count": 0,
                "file_size": os.path.getsize(file_path)
            },
            "error": None
        }
        
        try:
            # 파일 이름 가져오기
            file_name = os.path.basename(file_path)
            
            logger.info(f"PDF 파일 '{file_name}' OCR 처리 시작")
            
            # 파일을 base64로 인코딩
            with open(file_path, "rb") as pdf_file:
                file_content = pdf_file.read()
                file_base64 = base64.b64encode(file_content).decode("utf-8")
            
            # 요청 ID 생성
            request_id = str(uuid.uuid4())
            
            # API 요청 데이터 준비
            payload = {
                "model": "mistral-large-pdf",  # Mistral OCR 모델
                "id": request_id,
                "document": {
                    "type": "document_base64",
                    "document_base64": file_base64,
                    "document_name": file_name
                },
                "include_image_base64": include_images,
                "image_limit": image_limit,
                "image_min_size": image_min_size
            }
            
            # 페이지 범위 지정이 있는 경우 추가
            if pages is not None:
                payload["pages"] = pages
            
            # 실제 API 호출
            logger.info("Mistral OCR API 호출 중...")
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            
            # 응답 확인
            if response.status_code != 200:
                error_msg = f"API 호출 실패: 상태 코드 {response.status_code}"
                
                # 오류 응답 상세 정보 추출 시도
                try:
                    error_detail = response.json()
                    if "detail" in error_detail:
                        error_msg += f", 상세 정보: {json.dumps(error_detail['detail'])}"
                    else:
                        error_msg += f", 응답: {response.text[:200]}"
                except:
                    error_msg += f", 응답: {response.text[:200]}"
                
                logger.error(error_msg)
                result["error"] = error_msg
                return result
            
            # 응답 데이터 파싱
            response_data = response.json()
            
            # 응답 처리
            if "pages" in response_data:
                result["pages"] = response_data["pages"]
                result["metadata"]["page_count"] = len(response_data["pages"])
                
                # 전체 텍스트 및 마크다운 추출
                all_text = []
                all_markdown = []
                all_images = []
                
                for page in response_data["pages"]:
                    page_index = page.get("index", 0)
                    page_markdown = page.get("markdown", "")
                    
                    # 마크다운에서 일반 텍스트 추출
                    page_text = self._markdown_to_text(page_markdown)
                    
                    all_text.append(page_text)
                    all_markdown.append(f"## 페이지 {page_index + 1}\n\n{page_markdown}")
                    
                    # 이미지 처리
                    if include_images and "images" in page:
                        for img in page["images"]:
                            img["page"] = page_index
                            all_images.append(img)
                
                result["text"] = "\n\n".join(all_text)
                result["markdown"] = "\n\n".join(all_markdown)
                result["images"] = all_images
                
                # 추가 메타데이터 설정
                if "usage_info" in response_data:
                    result["metadata"]["usage_info"] = response_data["usage_info"]
                
                if "model" in response_data:
                    result["metadata"]["model"] = response_data["model"]
                
                # 페이지 차원 정보 추가
                page_dimensions = []
                for page in response_data["pages"]:
                    if "dimensions" in page:
                        page_dimensions.append({
                            "page": page.get("index", 0),
                            "dimensions": page["dimensions"]
                        })
                
                if page_dimensions:
                    result["metadata"]["page_dimensions"] = page_dimensions
                
                logger.info(f"PDF 처리 완료: {len(all_text)} 페이지, {len(all_images)} 이미지")
            else:
                result["error"] = "OCR 처리 결과에 페이지 정보가 없습니다."
        
        except Exception as e:
            logger.error(f"PDF 처리 중 오류 발생: {str(e)}")
            result["error"] = f"PDF 처리 중 오류가 발생했습니다: {str(e)}"
        
        return result
    
    def process_pdf_pages(self, file_path: str, page_ranges: str, include_images: bool = False,
                         image_limit: int = 10, image_min_size: int = 100) -> Dict[str, Any]:
        """
        PDF 파일의 특정 페이지 범위를 처리합니다.
        
        Args:
            file_path: PDF 파일 경로
            page_ranges: 처리할 페이지 범위 (예: "0-5,7,9-12")
            include_images: 이미지 포함 여부
            image_limit: 추출할 최대 이미지 수
            image_min_size: 추출할 이미지의 최소 크기(픽셀)
            
        Returns:
            Dict[str, Any]: 추출된 정보를 담은 딕셔너리
        """
        # 페이지 범위 파싱
        pages = self._parse_page_ranges(page_ranges)
        
        # 페이지 범위가 유효한 경우 처리
        if pages:
            return self.process_pdf(
                file_path=file_path,
                include_images=include_images,
                image_limit=image_limit,
                image_min_size=image_min_size,
                pages=pages
            )
        else:
            # 페이지 범위가 유효하지 않은 경우 오류 반환
            return {
                "text": "",
                "markdown": "",
                "images": [],
                "pages": [],
                "metadata": {
                    "page_count": 0,
                    "file_size": os.path.getsize(file_path)
                },
                "error": f"유효하지 않은 페이지 범위: {page_ranges}"
            }
    
    def _parse_page_ranges(self, page_ranges: str) -> List[int]:
        """
        페이지 범위 문자열을 파싱하여 페이지 목록을 반환합니다.
        
        Args:
            page_ranges: 페이지 범위 문자열 (예: "0-5,7,9-12")
            
        Returns:
            List[int]: 페이지 목록
        """
        pages = []
        
        try:
            # 쉼표로 구분된 범위 처리
            for range_str in page_ranges.split(','):
                range_str = range_str.strip()
                
                # 범위 (예: "0-5")
                if '-' in range_str:
                    start, end = map(int, range_str.split('-'))
                    pages.extend(range(start, end + 1))
                # 단일 페이지 (예: "7")
                else:
                    pages.append(int(range_str))
            
            # 중복 제거 및 정렬
            pages = sorted(list(set(pages)))
            
            return pages
        except ValueError:
            logger.error(f"페이지 범위 파싱 오류: {page_ranges}")
            return []
    
    def _markdown_to_text(self, markdown: str) -> str:
        """
        마크다운 텍스트에서 일반 텍스트를 추출합니다.
        
        Args:
            markdown: 마크다운 텍스트
            
        Returns:
            str: 추출된 일반 텍스트
        """
        # 간단한 마크다운 변환 (실제로는 더 복잡한 처리 필요)
        text = markdown
        
        # 헤더 처리
        for i in range(6, 0, -1):
            heading = '#' * i
            text = text.replace(f"{heading} ", "")
        
        # 강조 처리
        text = text.replace("**", "").replace("__", "")
        text = text.replace("*", "").replace("_", "")
        
        # 링크 처리
        import re
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # 코드 블록 처리
        text = re.sub(r'```[^\n]*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)
        
        # 인라인 코드 처리
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # 표 처리 (간단한 처리)
        text = re.sub(r'\|[^\n]+\|\n\|[-:| ]+\|\n', '', text)
        text = re.sub(r'\|([^\n]+)\|', r'\1', text)
        
        return text
    
    def save_extracted_images(self, images: List[Dict[str, Any]], output_dir: str) -> List[str]:
        """
        추출된 이미지를 파일로 저장합니다.
        
        Args:
            images: 추출된 이미지 목록
            output_dir: 이미지를 저장할 디렉토리
            
        Returns:
            List[str]: 저장된 이미지 파일 경로 목록
        """
        saved_paths = []
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        for i, img in enumerate(images):
            if "image_base64" in img and img["image_base64"]:
                try:
                    # Base64 디코딩
                    img_data = base64.b64decode(img["image_base64"])
                    
                    # 파일 저장
                    page_num = img.get("page", 0)
                    img_path = os.path.join(output_dir, f"image_p{page_num}_{i+1}.png")
                    
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    
                    saved_paths.append(img_path)
                    
                except Exception as e:
                    logger.error(f"이미지 저장 중 오류 발생: {str(e)}")
        
        return saved_paths
    
    def extract_tables_from_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """
        마크다운에서 표를 추출합니다.
        
        Args:
            markdown: 마크다운 텍스트
            
        Returns:
            List[Dict[str, Any]]: 추출된 표 목록
        """
        tables = []
        
        # 마크다운 표 형식 찾기
        import re
        table_pattern = r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)'
        
        for i, match in enumerate(re.finditer(table_pattern, markdown)):
            table_md = match.group(1)
            
            # 표 파싱
            lines = table_md.strip().split('\n')
            headers = [cell.strip() for cell in lines[0].split('|')[1:-1]]
            
            rows = []
            for line in lines[2:]:  # 첫 번째 줄은 헤더, 두 번째 줄은 구분선
                if '|' in line:
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]
                    rows.append(cells)
            
            tables.append({
                "id": f"table_{i+1}",
                "headers": headers,
                "rows": rows,
                "markdown": table_md
            })
        
        return tables
    
    def convert_to_pandas(self, table: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        추출된 표를 pandas DataFrame으로 변환합니다.
        
        Args:
            table: 추출된 표 정보
            
        Returns:
            Optional[pd.DataFrame]: 변환된 DataFrame 또는 None
        """
        try:
            headers = table["headers"]
            rows = table["rows"]
            
            # DataFrame 생성
            df = pd.DataFrame(rows, columns=headers)
            return df
            
        except Exception as e:
            logger.error(f"DataFrame 변환 중 오류 발생: {str(e)}")
            return None 