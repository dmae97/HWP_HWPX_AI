import os
import tempfile
import logging
from typing import Dict, Any, List, Optional, Tuple, BinaryIO
import json
from pathlib import Path

from hwp_utils import HwpHandler
from analyzer import ProjectAnalyzer

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hwp_to_latex')

class HwpToLatexConverter:
    """
    HWP 파일을 LaTeX로 변환하는 클래스
    
    Chain-of-Thought 기반 알고리즘을 사용하여 문서 구조를 파악하고
    LaTeX 코드로 변환합니다.
    """
    
    def __init__(self, api_key: str):
        """
        HwpToLatexConverter 초기화
        
        Args:
            api_key: Gemini API 키
        """
        self.analyzer = ProjectAnalyzer(api_key)
        self.hwp_handler = HwpHandler()
    
    def convert_file(self, file_obj: BinaryIO, template_type: str = "report") -> Dict[str, str]:
        """
        HWP 파일을 LaTeX로 변환합니다.
        
        Args:
            file_obj: HWP 파일 객체
            template_type: LaTeX 템플릿 유형 ("report", "article", "beamer" 등)
            
        Returns:
            Dict[str, str]: 변환 결과 (메인 LaTeX 코드 및 추출된 이미지 등)
        """
        try:
            # 1. HWP 파일에서 텍스트 및 메타데이터 추출
            text = HwpHandler.extract_text(file_obj)
            metadata = HwpHandler.extract_metadata(file_obj)
            
            # 2. 문서 구조 파악 (CoT 1단계)
            document_structure = self._extract_document_structure(text)
            
            # 3. LaTeX 코드 생성 (CoT 2단계)
            latex_code = self._generate_latex_code(document_structure, metadata, template_type)
            
            # 4. 결과 반환
            return {
                "latex_code": latex_code,
                "document_structure": document_structure,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"HWP 파일 변환 중 오류 발생: {str(e)}")
            raise
    
    def _extract_document_structure(self, text: str) -> Dict[str, Any]:
        """
        CoT 1단계: 텍스트에서 문서 구조를 파악합니다.
        
        Args:
            text: HWP 파일에서 추출한 텍스트
            
        Returns:
            Dict[str, Any]: 문서 구조 정보
        """
        logger.info("문서 구조 파악 중...")
        
        # 텍스트가 너무 길면 청크로 나누어 처리
        chunks = self._split_text_into_chunks(text, max_chunk_size=10000)
        
        # 각 청크에 대해 구조 파악
        chunk_structures = []
        for i, chunk in enumerate(chunks):
            logger.info(f"청크 {i+1}/{len(chunks)} 처리 중...")
            
            prompt = f"""
            다음은 국책과제 보고서의 일부 텍스트입니다. 이 텍스트의 구조를 분석하여 다음 정보를 JSON 형식으로 추출해주세요:
            
            1. 섹션 제목과 계층 구조 (장, 절, 소절 등)
            2. 표와 그림의 위치 및 캡션
            3. 수식이 있는 경우 그 위치와 내용
            4. 참고문헌이 있는 경우 그 목록
            
            텍스트:
            {chunk}
            
            JSON 형식으로 응답해주세요:
            {{
                "sections": [
                    {{
                        "level": 1,
                        "title": "섹션 제목",
                        "content": "섹션 내용 요약",
                        "subsections": [...]
                    }},
                    ...
                ],
                "tables": [
                    {{
                        "caption": "표 제목",
                        "content": "표 내용 설명"
                    }},
                    ...
                ],
                "figures": [...],
                "equations": [...],
                "references": [...]
            }}
            """
            
            response = self.analyzer._generate_response(prompt)
            
            # JSON 응답 파싱
            try:
                structure = json.loads(response)
                chunk_structures.append(structure)
            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패, 텍스트 응답 사용: {response[:100]}...")
                # JSON 파싱 실패 시 텍스트 응답 그대로 사용
                chunk_structures.append({"raw_response": response})
        
        # 청크별 구조 정보 통합
        combined_structure = self._combine_chunk_structures(chunk_structures)
        
        return combined_structure
    
    def _generate_latex_code(self, document_structure: Dict[str, Any], 
                            metadata: Dict[str, Any], template_type: str) -> str:
        """
        CoT 2단계: 파악된 문서 구조를 LaTeX 코드로 변환합니다.
        
        Args:
            document_structure: 문서 구조 정보
            metadata: 문서 메타데이터
            template_type: LaTeX 템플릿 유형
            
        Returns:
            str: 생성된 LaTeX 코드
        """
        logger.info("LaTeX 코드 생성 중...")
        
        # 문서 구조와 메타데이터를 JSON 문자열로 변환
        structure_json = json.dumps(document_structure, ensure_ascii=False, indent=2)
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        
        prompt = f"""
        다음은 국책과제 보고서의 구조 분석 결과와 메타데이터입니다. 
        이를 LaTeX 코드로 변환해주세요.
        
        템플릿 유형: {template_type}
        
        메타데이터:
        {metadata_json}
        
        문서 구조:
        {structure_json}
        
        다음 규칙을 따라 LaTeX 코드를 생성해주세요:
        1. 템플릿 유형이 "report"인 경우 \\documentclass{{report}}를, "article"인 경우 \\documentclass{{article}}를 사용
        2. 한글 지원을 위해 kotex 패키지 포함
        3. 표는 tabular 환경, 그림은 figure 환경, 수식은 equation 환경 사용
        4. 참고문헌은 thebibliography 환경 사용
        5. 메타데이터의 제목, 저자, 날짜 정보를 title, author, date 명령에 사용
        
        전체 LaTeX 코드를 생성해주세요.
        """
        
        latex_code = self.analyzer._generate_response(prompt)
        
        # LaTeX 코드 검증 및 수정
        latex_code = self._verify_and_fix_latex(latex_code)
        
        return latex_code
    
    def _verify_and_fix_latex(self, latex_code: str) -> str:
        """
        생성된 LaTeX 코드를 검증하고 필요한 경우 수정합니다.
        
        Args:
            latex_code: 생성된 LaTeX 코드
            
        Returns:
            str: 검증 및 수정된 LaTeX 코드
        """
        # 기본 패키지가 포함되어 있는지 확인
        required_packages = [
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage[T1]{fontenc}",
            "\\usepackage{kotex}",
            "\\usepackage{graphicx}",
            "\\usepackage{amsmath}"
        ]
        
        # 문서 클래스 선언 확인
        if "\\documentclass" not in latex_code:
            latex_code = "\\documentclass{report}\n" + latex_code
        
        # 필요한 패키지 추가
        package_section_end = latex_code.find("\\begin{document}")
        if package_section_end == -1:
            # 문서 시작 태그가 없으면 추가
            if "\\title" in latex_code:
                # title 명령 앞에 삽입
                title_pos = latex_code.find("\\title")
                latex_code = latex_code[:title_pos] + "\n\\begin{document}\n" + latex_code[title_pos:]
            else:
                # 없으면 맨 앞에 추가
                latex_code = "\\begin{document}\n" + latex_code
            package_section_end = latex_code.find("\\begin{document}")
        
        # 필요한 패키지 추가
        for package in required_packages:
            if package not in latex_code:
                latex_code = latex_code[:package_section_end] + package + "\n" + latex_code[package_section_end:]
        
        # 문서 종료 태그 확인
        if "\\end{document}" not in latex_code:
            latex_code += "\n\\end{document}"
        
        return latex_code
    
    def _split_text_into_chunks(self, text: str, max_chunk_size: int = 10000) -> List[str]:
        """
        긴 텍스트를 처리 가능한 청크로 나눕니다.
        
        Args:
            text: 원본 텍스트
            max_chunk_size: 최대 청크 크기
            
        Returns:
            List[str]: 텍스트 청크 목록
        """
        # 텍스트가 최대 크기보다 작으면 그대로 반환
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        
        # 단락 또는 줄바꿈을 기준으로 나누기
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            # 현재 청크에 단락을 추가했을 때 최대 크기를 초과하는지 확인
            if len(current_chunk) + len(paragraph) + 2 <= max_chunk_size:
                if current_chunk:
                    current_chunk += '\n\n'
                current_chunk += paragraph
            else:
                # 현재 청크가 비어있지 않으면 청크 목록에 추가
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 새 청크 시작
                # 단락이 최대 크기보다 크면 더 작게 나누기
                if len(paragraph) > max_chunk_size:
                    # 줄바꿈으로 나누기
                    lines = paragraph.split('\n')
                    current_chunk = ""
                    
                    for line in lines:
                        if len(current_chunk) + len(line) + 1 <= max_chunk_size:
                            if current_chunk:
                                current_chunk += '\n'
                            current_chunk += line
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            
                            # 라인이 여전히 너무 길면 단어 단위로 나누기
                            if len(line) > max_chunk_size:
                                words = line.split(' ')
                                current_chunk = ""
                                
                                for word in words:
                                    if len(current_chunk) + len(word) + 1 <= max_chunk_size:
                                        if current_chunk:
                                            current_chunk += ' '
                                        current_chunk += word
                                    else:
                                        chunks.append(current_chunk)
                                        current_chunk = word
                            else:
                                current_chunk = line
                else:
                    current_chunk = paragraph
        
        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _combine_chunk_structures(self, chunk_structures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        여러 청크에서 추출한 구조 정보를 하나로 통합합니다.
        
        Args:
            chunk_structures: 청크별 구조 정보 목록
            
        Returns:
            Dict[str, Any]: 통합된 구조 정보
        """
        # 기본 통합 구조
        combined = {
            "sections": [],
            "tables": [],
            "figures": [],
            "equations": [],
            "references": []
        }
        
        # 각 청크의 구조 정보 통합
        for structure in chunk_structures:
            # raw_response인 경우 건너뛰기
            if "raw_response" in structure:
                continue
                
            # 섹션 통합
            if "sections" in structure:
                combined["sections"].extend(structure["sections"])
            
            # 표 통합
            if "tables" in structure:
                combined["tables"].extend(structure["tables"])
            
            # 그림 통합
            if "figures" in structure:
                combined["figures"].extend(structure["figures"])
            
            # 수식 통합
            if "equations" in structure:
                combined["equations"].extend(structure["equations"])
            
            # 참고문헌 통합
            if "references" in structure:
                combined["references"].extend(structure["references"])
        
        return combined
    
    def generate_template(self, template_type: str = "report", 
                         project_info: Dict[str, str] = None) -> str:
        """
        국책과제 보고서를 위한 LaTeX 템플릿을 생성합니다.
        
        Args:
            template_type: 템플릿 유형 ("report", "article", "beamer" 등)
            project_info: 프로젝트 정보 (제목, 저자, 초록 등)
            
        Returns:
            str: 생성된 LaTeX 템플릿 코드
        """
        if project_info is None:
            project_info = {
                "title": "국책과제 보고서",
                "author": "연구책임자",
                "abstract": "이 보고서는 국책과제의 연구 결과를 정리한 것입니다.",
                "keywords": "국책과제, 연구, 보고서"
            }
        
        if template_type == "report":
            template = f"""\\documentclass[a4paper,12pt]{{report}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{kotex}}
\\usepackage{{graphicx}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{booktabs}}
\\usepackage{{hyperref}}
\\usepackage{{fancyhdr}}

\\title{{{project_info.get("title", "국책과제 보고서")}}}
\\author{{{project_info.get("author", "연구책임자")}}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
{project_info.get("abstract", "이 보고서는 국책과제의 연구 결과를 정리한 것입니다.")}
\\end{{abstract}}

\\tableofcontents
\\newpage

\\chapter{{서론}}
\\section{{연구 배경}}
연구 배경에 대한 내용을 작성하세요.

\\section{{연구 목표}}
연구 목표에 대한 내용을 작성하세요.

\\chapter{{연구 내용 및 방법}}
연구 내용 및 방법에 대한 내용을 작성하세요.

\\chapter{{연구 결과}}
연구 결과에 대한 내용을 작성하세요.

\\chapter{{결론 및 향후 계획}}
결론 및 향후 계획에 대한 내용을 작성하세요.

\\begin{{thebibliography}}{{99}}
\\bibitem{{ref1}} 참고문헌 1
\\bibitem{{ref2}} 참고문헌 2
\\end{{thebibliography}}

\\end{{document}}
"""
        elif template_type == "article":
            template = f"""\\documentclass[a4paper,12pt]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{kotex}}
\\usepackage{{graphicx}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{booktabs}}
\\usepackage{{hyperref}}
\\usepackage{{fancyhdr}}

\\title{{{project_info.get("title", "국책과제 보고서")}}}
\\author{{{project_info.get("author", "연구책임자")}}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
{project_info.get("abstract", "이 보고서는 국책과제의 연구 결과를 정리한 것입니다.")}
\\end{{abstract}}

\\tableofcontents
\\newpage

\\section{{서론}}
\\subsection{{연구 배경}}
연구 배경에 대한 내용을 작성하세요.

\\subsection{{연구 목표}}
연구 목표에 대한 내용을 작성하세요.

\\section{{연구 내용 및 방법}}
연구 내용 및 방법에 대한 내용을 작성하세요.

\\section{{연구 결과}}
연구 결과에 대한 내용을 작성하세요.

\\section{{결론 및 향후 계획}}
결론 및 향후 계획에 대한 내용을 작성하세요.

\\begin{{thebibliography}}{{99}}
\\bibitem{{ref1}} 참고문헌 1
\\bibitem{{ref2}} 참고문헌 2
\\end{{thebibliography}}

\\end{{document}}
"""
        else:
            raise ValueError(f"지원하지 않는 템플릿 유형: {template_type}")
        
        return template
    
    def save_latex_to_file(self, latex_code: str, output_path: str) -> str:
        """
        생성된 LaTeX 코드를 파일로 저장합니다.
        
        Args:
            latex_code: LaTeX 코드
            output_path: 출력 파일 경로
            
        Returns:
            str: 저장된 파일 경로
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(latex_code)
            logger.info(f"LaTeX 코드가 {output_path}에 저장되었습니다.")
            return output_path
        except Exception as e:
            logger.error(f"LaTeX 코드 저장 중 오류 발생: {str(e)}")
            raise

# 테스트 함수
def test_hwp_to_latex(hwp_file_path: str, output_dir: str = None):
    """
    HWP 파일을 LaTeX로 변환하는 테스트 함수
    
    Args:
        hwp_file_path: HWP 파일 경로
        output_dir: 출력 디렉토리 (기본값: 현재 디렉토리)
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")
    
    converter = HwpToLatexConverter(api_key)
    
    # 출력 디렉토리 설정
    if output_dir is None:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)
    
    # HWP 파일 열기
    with open(hwp_file_path, 'rb') as f:
        # LaTeX로 변환
        result = converter.convert_file(f)
        
        # 결과 저장
        output_path = os.path.join(output_dir, Path(hwp_file_path).stem + '.tex')
        converter.save_latex_to_file(result["latex_code"], output_path)
        
        # 구조 정보 저장
        structure_path = os.path.join(output_dir, Path(hwp_file_path).stem + '_structure.json')
        with open(structure_path, 'w', encoding='utf-8') as f:
            json.dump(result["document_structure"], f, ensure_ascii=False, indent=2)
        
        print(f"변환 완료: {output_path}")
        print(f"구조 정보: {structure_path}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python hwp_to_latex.py <hwp_file_path> [output_dir]")
        sys.exit(1)
    
    hwp_file_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    test_hwp_to_latex(hwp_file_path, output_dir) 