import os
import tempfile
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from document_handler import DocumentProcessorFactory
import uvicorn
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("document_api")

# FastAPI 앱 생성
app = FastAPI(
    title="문서 처리 API",
    description="HWP, HWPX, PDF 등 다양한 문서 형식을 처리하는 API",
    version="1.0.0"
)

# API 키 가져오기
def get_api_keys():
    """API 키를 환경 변수에서 가져옵니다."""
    return {
        "MISTRAL_API_KEY": os.environ.get("MISTRAL_API_KEY", ""),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
        "PERPLEXITY_API_KEY": os.environ.get("PERPLEXITY_API_KEY", "")
    }

# 응답 모델
class DocumentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# 문서 처리 엔드포인트
@app.post("/api/process-document", response_model=DocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    include_images: bool = Form(False),
    image_limit: int = Form(10),
    image_min_size: int = Form(100),
    pages: str = Form(None)
):
    """
    문서 파일을 처리하여 텍스트, 메타데이터, 표, 이미지 등을 추출합니다.
    
    - **file**: 처리할 문서 파일 (HWP, HWPX, PDF 등)
    - **include_images**: 이미지 포함 여부
    - **image_limit**: 추출할 최대 이미지 수
    - **image_min_size**: 추출할 이미지의 최소 크기(픽셀)
    - **pages**: 처리할 페이지 범위 (예: "0-5,7,9-12")
    """
    try:
        # API 키 가져오기
        api_keys = get_api_keys()
        
        # Mistral API 키 확인
        if not api_keys["MISTRAL_API_KEY"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Mistral API 키가 설정되지 않았습니다.", "error": "API_KEY_MISSING"}
            )
        
        # 파일 확장자 확인
        file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        if file_ext not in ["pdf", "hwp", "hwpx"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "지원되지 않는 파일 형식입니다.", "error": "UNSUPPORTED_FILE_TYPE"}
            )
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_path = temp_file.name
        
        try:
            # 페이지 범위 파싱
            page_list = None
            if pages:
                # 페이지 범위 문자열을 정수 리스트로 변환
                page_list = []
                for range_str in pages.split(','):
                    range_str = range_str.strip()
                    if '-' in range_str:
                        start, end = map(int, range_str.split('-'))
                        page_list.extend(range(start, end + 1))
                    else:
                        page_list.append(int(range_str))
                page_list = sorted(list(set(page_list)))
            
            # 문서 처리기 생성 (API 환경에 최적화)
            handler = DocumentProcessorFactory.get_handler_for_api(file_ext, api_keys)
            
            # 파일 처리
            with open(temp_path, "rb") as file_obj:
                result = handler.process_document(
                    file_obj,
                    include_images=include_images,
                    image_limit=image_limit,
                    image_min_size=image_min_size,
                    pages=page_list
                )
            
            # 이미지 데이터 처리 (Base64로 변환)
            if "images" in result and result["images"]:
                import base64
                encoded_images = []
                for img_bytes in result["images"]:
                    encoded = base64.b64encode(img_bytes).decode("utf-8")
                    encoded_images.append(encoded)
                result["images"] = encoded_images
            
            # 원본 API 응답 제거 (용량 감소)
            if "raw_response" in result:
                del result["raw_response"]
            
            return {
                "success": True,
                "message": "문서 처리가 완료되었습니다.",
                "data": result,
                "error": None
            }
            
        finally:
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
    
    except Exception as e:
        logger.error(f"문서 처리 중 오류 발생: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "문서 처리 중 오류가 발생했습니다.",
                "error": str(e)
            }
        )

# 텍스트 추출 엔드포인트
@app.post("/api/extract-text", response_model=DocumentResponse)
async def extract_text(
    file: UploadFile = File(...),
    pages: str = Form(None)
):
    """
    문서 파일에서 텍스트만 추출합니다.
    
    - **file**: 처리할 문서 파일 (HWP, HWPX, PDF 등)
    - **pages**: 처리할 페이지 범위 (예: "0-5,7,9-12")
    """
    try:
        # API 키 가져오기
        api_keys = get_api_keys()
        
        # Mistral API 키 확인
        if not api_keys["MISTRAL_API_KEY"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Mistral API 키가 설정되지 않았습니다.", "error": "API_KEY_MISSING"}
            )
        
        # 파일 확장자 확인
        file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        if file_ext not in ["pdf", "hwp", "hwpx"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "지원되지 않는 파일 형식입니다.", "error": "UNSUPPORTED_FILE_TYPE"}
            )
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_path = temp_file.name
        
        try:
            # 문서 처리기 생성 (API 환경에 최적화)
            handler = DocumentProcessorFactory.get_handler_for_api(file_ext, api_keys)
            
            # 파일에서 텍스트 추출
            with open(temp_path, "rb") as file_obj:
                text = handler.extract_text(file_obj)
            
            return {
                "success": True,
                "message": "텍스트 추출이 완료되었습니다.",
                "data": {"text": text},
                "error": None
            }
            
        finally:
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
    
    except Exception as e:
        logger.error(f"텍스트 추출 중 오류 발생: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "텍스트 추출 중 오류가 발생했습니다.",
                "error": str(e)
            }
        )

# 메타데이터 추출 엔드포인트
@app.post("/api/extract-metadata", response_model=DocumentResponse)
async def extract_metadata(
    file: UploadFile = File(...)
):
    """
    문서 파일에서 메타데이터만 추출합니다.
    
    - **file**: 처리할 문서 파일 (HWP, HWPX, PDF 등)
    """
    try:
        # API 키 가져오기
        api_keys = get_api_keys()
        
        # Mistral API 키 확인
        if not api_keys["MISTRAL_API_KEY"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Mistral API 키가 설정되지 않았습니다.", "error": "API_KEY_MISSING"}
            )
        
        # 파일 확장자 확인
        file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        if file_ext not in ["pdf", "hwp", "hwpx"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "지원되지 않는 파일 형식입니다.", "error": "UNSUPPORTED_FILE_TYPE"}
            )
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_path = temp_file.name
        
        try:
            # 문서 처리기 생성 (API 환경에 최적화)
            handler = DocumentProcessorFactory.get_handler_for_api(file_ext, api_keys)
            
            # 파일에서 메타데이터 추출
            with open(temp_path, "rb") as file_obj:
                metadata = handler.extract_metadata(file_obj)
            
            return {
                "success": True,
                "message": "메타데이터 추출이 완료되었습니다.",
                "data": {"metadata": metadata},
                "error": None
            }
            
        finally:
            # 임시 파일 삭제
            try:
                os.unlink(temp_path)
            except:
                pass
    
    except Exception as e:
        logger.error(f"메타데이터 추출 중 오류 발생: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "메타데이터 추출 중 오류가 발생했습니다.",
                "error": str(e)
            }
        )

# 상태 확인 엔드포인트
@app.get("/api/status")
async def get_status():
    """API 상태를 확인합니다."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "supported_formats": ["pdf", "hwp", "hwpx"]
    }

# 메인 실행 코드
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 