import os
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional, Tuple
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
import re
from datetime import datetime
import tempfile
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 로깅 설정
logger = logging.getLogger(__name__)

try:
    # PDF 생성 라이브러리 임포트
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    # 한글 폰트 등록 시도
    try:
        # 윈도우 환경
        if os.name == 'nt':
            pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
        # 리눅스 환경
        else:
            # 여러 가능한 경로 시도
            font_paths = [
                '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # 대체 폰트
                '/usr/share/fonts/TTF/DejaVuSans.ttf'  # 대체 폰트
            ]
            
            font_registered = False
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
                        font_registered = True
                        logger.info(f"폰트 등록 성공: {font_path}")
                        break
                except Exception as e:
                    logger.warning(f"폰트 등록 시도 실패 ({font_path}): {str(e)}")
            
            # 모든 폰트 등록 시도 실패 시 기본 폰트 사용
            if not font_registered:
                logger.warning("모든 폰트 등록 시도 실패. 기본 폰트를 사용합니다.")
        
        PDF_SUPPORT = True
    except Exception as e:
        logger.warning(f"한글 폰트 등록 실패: {str(e)}. 기본 폰트를 사용합니다.")
        PDF_SUPPORT = True
        
except ImportError:
    logger.warning("reportlab 라이브러리가 설치되지 않아 PDF 출력 기능이 제한됩니다.")
    PDF_SUPPORT = False

# 분석 결과 저장 경로
ANALYSIS_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_history")
# 디렉토리가 없으면 생성
os.makedirs(ANALYSIS_HISTORY_DIR, exist_ok=True)

class ProjectAnalyzer:
    """
    국책과제 분석기 클래스
    Gemini API를 활용하여 국책과제 문서를 분석하고 인사이트를 제공합니다.
    Chain of Thought(CoT) 및 강화학습(RL) 기법을 적용하여 분석 품질을 향상시킵니다.
    """
    
    def __init__(self, api_key: str):
        """
        ProjectAnalyzer 초기화
        
        Args:
            api_key: Google Gemini API 키
        """
        self.api_key = api_key
        
        # Gemini 모델 설정
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-pro-exp-02-05",
            generation_config={
                "temperature": 0.2,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
        )
        
        # 텍스트 분할기 설정
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # 분석 템플릿 로드
        self.templates = self._load_analysis_templates()
        
        # 문서 타입별 분석 설정
        self.document_types = {
            "법률": {
                "identifiers": ["제", "조", "항", "호", "법률", "계약", "조항", "법원", "판결", "원고", "피고"],
                "structure": ["조문", "항목", "예외 사항", "벌칙", "부칙"],
                "focus_points": ["법적 유효성", "위험 요소", "의무 사항", "책임 소재"]
            },
            "논문": {
                "identifiers": ["초록", "서론", "방법", "결과", "고찰", "결론", "참고문헌", "연구", "가설"],
                "structure": ["초록", "서론", "연구방법", "연구결과", "고찰", "결론", "참고문헌"],
                "focus_points": ["연구 목적", "방법론 타당성", "결과 신뢰성", "결론 일관성"]
            },
            "국책과제": {
                "identifiers": ["사업", "계획", "목표", "예산", "추진", "성과", "지원", "과제", "평가"],
                "structure": ["사업 개요", "추진 계획", "예산", "기대효과", "성과지표"],
                "focus_points": ["목표 명확성", "예산 효율성", "성과 측정", "진행 상황"]
            }
        }
        
        # RL 보상 가중치 설정
        self.reward_weights = {
            "구조_인식": 0.2,    # 문서 구조를 잘 파악하는지
            "논리_일관성": 0.3,   # 분석 과정에서 논리적 모순이 없는지
            "근거_기반": 0.25,   # 원문 인용 등 근거를 제시하는지
            "정보_포괄성": 0.15,  # 문서의 핵심 정보를 누락없이 포함하는지
            "실용성": 0.1        # 제안 사항이 실제로 적용 가능한지
        }
        
        # 분석 이력 관리를 위한 설정
        self.analysis_history_dir = ANALYSIS_HISTORY_DIR
    
    def _load_analysis_templates(self) -> Dict[str, str]:
        """
        분석 템플릿을 로드합니다.
        
        Returns:
            템플릿 딕셔너리
        """
        # 기본 템플릿
        templates = {
            "standard": """
            당신은 국책과제 전문가 AI입니다. 다음 국책과제 문서를 분석하고 주요 내용, 요약, 권장사항을 제공해주세요.
            
            문서 내용:
            {text}
            
            다음 형식으로 분석 결과를 제공해주세요:
            1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
            2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
            3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
            
            각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
            """,
            
            "cot": """
            당신은 국책과제 전문가 AI입니다. 다음 국책과제 문서를 분석하고 주요 내용, 요약, 권장사항을 제공해주세요.
            
            문서 내용:
            {text}
            
            단계별로 생각해보겠습니다:
            
            1. 문서 구조 파악:
            - 문서의 전체적인 구조는 어떻게 되어 있는가?
            - 주요 섹션과 하위 섹션은 무엇인가?
            
            2. 핵심 정보 추출:
            - 국책과제의 목적은 무엇인가?
            - 배경 및 필요성은 무엇인가?
            - 주요 내용 및 추진 방향은 무엇인가?
            - 예산 및 기간은 어떻게 되는가?
            - 참여 기관 및 역할은 무엇인가?
            - 기대 효과 및 활용 방안은 무엇인가?
            
            3. 정보 분석 및 연결:
            - 추출한 정보들 간의 연관성은 무엇인가?
            - 국책과제의 강점과 약점은 무엇인가?
            - 국책과제의 성공 가능성에 영향을 미치는 요소는 무엇인가?
            
            4. 결론 도출:
            - 국책과제의 전반적인 평가는 어떠한가?
            - 국책과제의 성공적인 수행을 위한 권장사항은 무엇인가?
            
            위 단계에 따라 분석한 후, 다음 형식으로 최종 분석 결과를 제공해주세요:
            1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
            2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
            3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
            
            각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
            """,
            
            "rl": """
            당신은 국책과제 전문가 AI입니다. 다음 국책과제 문서를 분석하고 주요 내용, 요약, 권장사항을 제공해주세요.
            
            문서 내용:
            {text}
            
            다음 지침에 따라 분석을 수행하세요:
            
            1. 분석의 정확성과 완전성을 최우선으로 합니다.
            2. 국책과제의 모든 중요한 측면을 포함해야 합니다.
            3. 객관적이고 균형 잡힌 분석을 제공해야 합니다.
            4. 명확하고 구조화된 형식으로 정보를 제시해야 합니다.
            5. 실행 가능하고 구체적인 권장사항을 제공해야 합니다.
            
            위 지침을 따르면 높은 보상을 받게 됩니다. 반면, 다음과 같은 행동은 낮은 보상을 받게 됩니다:
            - 중요한 정보 누락
            - 부정확한 정보 제공
            - 모호하거나 구체적이지 않은 분석
            - 비구조화된 형식으로 정보 제시
            - 실행 불가능하거나 모호한 권장사항 제공
            
            다음 형식으로 분석 결과를 제공해주세요:
            1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
            2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
            3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
            
            각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
            """,
            
            "hybrid": """
            당신은 국책과제 전문가 AI입니다. 다음 국책과제 문서를 분석하고 주요 내용, 요약, 권장사항을 제공해주세요.
            
            문서 내용:
            {text}
            
            단계별로 생각해보겠습니다:
            
            1. 문서 구조 파악:
            - 문서의 전체적인 구조는 어떻게 되어 있는가?
            - 주요 섹션과 하위 섹션은 무엇인가?
            
            2. 핵심 정보 추출:
            - 국책과제의 목적은 무엇인가?
            - 배경 및 필요성은 무엇인가?
            - 주요 내용 및 추진 방향은 무엇인가?
            - 예산 및 기간은 어떻게 되는가?
            - 참여 기관 및 역할은 무엇인가?
            - 기대 효과 및 활용 방안은 무엇인가?
            
            3. 정보 분석 및 연결:
            - 추출한 정보들 간의 연관성은 무엇인가?
            - 국책과제의 강점과 약점은 무엇인가?
            - 국책과제의 성공 가능성에 영향을 미치는 요소는 무엇인가?
            
            4. 결론 도출:
            - 국책과제의 전반적인 평가는 어떠한가?
            - 국책과제의 성공적인 수행을 위한 권장사항은 무엇인가?
            
            다음 지침에 따라 분석을 수행하세요:
            
            1. 분석의 정확성과 완전성을 최우선으로 합니다.
            2. 국책과제의 모든 중요한 측면을 포함해야 합니다.
            3. 객관적이고 균형 잡힌 분석을 제공해야 합니다.
            4. 명확하고 구조화된 형식으로 정보를 제시해야 합니다.
            5. 실행 가능하고 구체적인 권장사항을 제공해야 합니다.
            
            위 단계와 지침에 따라 분석한 후, 다음 형식으로 최종 분석 결과를 제공해주세요:
            1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
            2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
            3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
            
            각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
            """
        }
        
        return templates
    
    def _split_text(self, text: str) -> List[str]:
        """
        긴 텍스트를 처리 가능한 청크로 분할합니다.
        
        Args:
            text: 분할할 텍스트
            
        Returns:
            텍스트 청크 목록
        """
        return self.text_splitter.split_text(text)
    
    def _generate_response(self, prompt: str) -> str:
        """
        Gemini 모델을 사용하여 프롬프트에 대한 응답을 생성합니다.
        
        Args:
            prompt: 모델에 전달할 프롬프트
            
        Returns:
            모델이 생성한 응답 텍스트
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"응답 생성 중 오류 발생: {str(e)}")
            return f"응답 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """
        텍스트에서 분석, 요약, 권장사항 섹션을 추출합니다.
        
        Args:
            text: 추출할 텍스트
            
        Returns:
            섹션 딕셔너리
        """
        sections = {
            "analysis": "",
            "summary": "",
            "recommendations": ""
        }
        
        # 상세 분석 섹션 추출
        analysis_match = re.search(r'(?:상세\s*분석|분석\s*결과)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=(?:요약|요점|주요\s*내용|권장\s*사항|$))', text, re.DOTALL)
        if analysis_match:
            sections["analysis"] = analysis_match.group(1).strip()
        
        # 요약 섹션 추출
        summary_match = re.search(r'(?:요약|요점|주요\s*내용)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=(?:권장\s*사항|제안|결론|$))', text, re.DOTALL)
        if summary_match:
            sections["summary"] = summary_match.group(1).strip()
        
        # 권장사항 섹션 추출
        recommendations_match = re.search(r'(?:권장\s*사항|제안|결론)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=$)', text, re.DOTALL)
        if recommendations_match:
            sections["recommendations"] = recommendations_match.group(1).strip()
        
        return sections
    
    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """
        텍스트에서 특정 섹션을 추출합니다.
        
        Args:
            text: 추출할 텍스트
            section_name: 섹션 이름
            
        Returns:
            추출된 섹션 텍스트 또는 None
        """
        # 섹션 이름에 따른 정규식 패턴 설정
        if section_name == "상세 분석":
            pattern = r'(?:상세\s*분석|분석\s*결과)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=(?:요약|요점|주요\s*내용|권장\s*사항|$))'
        elif section_name == "요약":
            pattern = r'(?:요약|요점|주요\s*내용)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=(?:권장\s*사항|제안|결론|$))'
        elif section_name == "권장사항":
            pattern = r'(?:권장\s*사항|제안|결론)(?:\s*[:：]\s*|\s*\n+\s*)(.*?)(?=$)'
        else:
            return None
        
        # 정규식으로 섹션 추출
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _detect_document_type(self, text: str) -> str:
        """
        문서 텍스트를 분석하여 문서 유형을 감지합니다.
        
        Args:
            text: 분석할 문서 텍스트
            
        Returns:
            감지된 문서 유형 ("법률", "논문", "국책과제" 중 하나)
        """
        # 각 문서 유형별 식별자 점수 계산
        type_scores = {}
        
        for doc_type, config in self.document_types.items():
            score = 0
            identifiers = config["identifiers"]
            
            # 텍스트 샘플링 (너무 긴 텍스트의 경우)
            sample_text = text[:10000] if len(text) > 10000 else text
            
            # 각 식별자의 출현 빈도 계산
            for identifier in identifiers:
                score += sample_text.count(identifier) * 1.5
                
            # 구조 키워드 존재 여부 확인
            for structure in config["structure"]:
                if structure in sample_text:
                    score += 5
                    
            type_scores[doc_type] = score
        
        # LLM 기반 문서 유형 판단 (백업 및 보완)
        llm_doc_type = self._llm_document_type_classification(text[:5000])
        
        # 최종 유형 판단
        if llm_doc_type in type_scores:
            type_scores[llm_doc_type] += 10
            
        # 가장 높은 점수의 문서 유형 반환
        if type_scores:
            return max(type_scores, key=type_scores.get)
        else:
            return "국책과제"  # 기본값
    
    def _llm_document_type_classification(self, text: str) -> str:
        """
        LLM을 사용하여 문서 유형을 분류합니다.
        
        Args:
            text: 분석할 문서 텍스트 (일부)
            
        Returns:
            문서 유형 ("법률", "논문", "국책과제" 중 하나)
        """
        prompt = f"""
        다음 문서 텍스트의 유형을 분류해주세요. 가능한 유형은 '법률', '논문', '국책과제' 중 하나입니다.
        
        텍스트:
        {text}
        
        각 유형의 특성:
        - 법률: 조항, 계약 조건, 법적 규정, 판례 등이 포함됨
        - 논문: 학술적 연구, 초록, 서론, 방법, 결과, 고찰 등의 구조를 가짐
        - 국책과제: 정부 지원 과제, 사업 계획, 예산, 추진 내용, 성과 등을 다룸
        
        분석 과정:
        1. 문서에 사용된 용어와 표현 검토
        2. 문서의 구조적 특징 분석
        3. 문서의 목적과 내용 평가
        
        위 분석을 통해 가장 적합한 문서 유형 하나만 선택해 주세요.
        답변 형식: "문서유형: [법률/논문/국책과제]"
        """
        
        try:
            response = self._generate_response(prompt)
            
            # 응답에서 문서 유형 추출
            if "법률" in response:
                return "법률"
            elif "논문" in response:
                return "논문"
            elif "국책과제" in response:
                return "국책과제"
            else:
                return "국책과제"  # 기본값
                
        except Exception as e:
            logger.error(f"문서 유형 분류 중 오류 발생: {str(e)}")
            return "국책과제"  # 오류 발생 시 기본값
            
    def _cot_analyze_document(self, text: str, doc_type: str, method: str = "hybrid") -> Dict[str, Any]:
        """
        Chain-of-Thought 방식으로 문서를 분석합니다.
        
        Args:
            text: 분석할 문서 텍스트
            doc_type: 문서 유형 ("법률", "논문", "국책과제" 중 하나)
            method: 분석 방법
            
        Returns:
            CoT 분석 결과를 포함한 딕셔너리
        """
        # 문서 유형별 맞춤 프롬프트 구성
        type_specific_prompt = ""
        
        if doc_type == "법률":
            type_specific_prompt = """
            법률 문서 분석을 위한 추가 지침:
            1. 조항별 주요 내용과 의미를 정리하세요.
            2. 법적 책임과 의무 사항을 명확히 식별하세요.
            3. 잠재적 법적 리스크나 모호한 부분을 표시하세요.
            4. 관련 법규나 판례와의 연관성을 검토하세요.
            """
        elif doc_type == "논문":
            type_specific_prompt = """
            학술 논문 분석을 위한 추가 지침:
            1. 연구 질문과 가설을 명확히 식별하세요.
            2. 연구 방법론의 타당성을 평가하세요.
            3. 결과의 통계적 의미와 함의를 검토하세요.
            4. 연구의 한계와 후속 연구 방향을 제시하세요.
            """
        else:  # 국책과제
            type_specific_prompt = """
            국책과제 문서 분석을 위한 추가 지침:
            1. 과제의 목표와 기대효과를 명확히 정리하세요.
            2. 예산 계획과 집행의 효율성을 평가하세요.
            3. 성과 지표와 평가 방법의 적절성을 검토하세요.
            4. 유사 사업과의 차별성과 혁신성을 분석하세요.
            """
            
        # Chain-of-Thought 분석 프롬프트 구성
        cot_prompt = f"""
        다음 문서를 Chain-of-Thought 방식으로 단계적으로 분석해주세요. 생각의 흐름을 명시적으로 표현하며 분석을 진행하세요.
        
        문서 유형: {doc_type}
        
        분석할 문서:
        {text}
        
        {type_specific_prompt}
        
        분석 과정을 다음 단계로 진행하세요:
        
        <think>
        1. 문서 구조 파악:
        - 전체적인 문서의 구조와 섹션을 식별합니다.
        - 각 섹션의 목적과 역할을 파악합니다.
        
        2. 핵심 정보 추출:
        - 문서의 주요 주장, 목표, 결과 등을 식별합니다.
        - 중요한 데이터, 숫자, 날짜 등을 추출합니다.
        
        3. 논리 흐름 분석:
        - 문서 내용의 논리적 일관성을 검토합니다.
        - 모순되는 내용이나 논리적 비약이 있는지 확인합니다.
        
        4. 비판적 평가:
        - 문서의 강점과 약점을 식별합니다.
        - 개선이 필요한 부분이나 보완할 사항을 제시합니다.
        </think>
        
        최종 분석 결과를 다음 형식으로 제공해주세요:
        1. 요약: 문서의 핵심 내용을 간결하게 요약
        2. 상세 분석: 문서의 주요 내용을 섹션별로 분석
        3. 평가: 문서의 강점과 약점, 논리적 일관성 평가
        4. 제안사항: 개선이나 보완이 필요한 사항
        
        모든 분석은 원문에서 충분한 근거를 제시하고, 주관적 판단보다는 객관적 분석에 중점을 두세요.
        """
        
        # 분석 실행
        response = self._generate_response(cot_prompt)
        
        # 응답 파싱 및 구조화
        result = self._extract_sections(response)
        
        # think 태그 내용 추출 (내부 추론 과정)
        thinking = self._extract_between_tags(response, "think")
        
        # 결과에 내부 추론 과정과 문서 유형 추가
        result["thinking_process"] = thinking if thinking else "내부 추론 과정을 추출할 수 없습니다."
        result["document_type"] = doc_type
        
        return result
        
    def _extract_between_tags(self, text: str, tag: str) -> Optional[str]:
        """
        텍스트에서 특정 태그 사이의 내용을 추출합니다.
        
        Args:
            text: 추출할 텍스트
            tag: 태그 이름 (예: "think")
            
        Returns:
            태그 사이의 내용 또는 None
        """
        import re
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        return None
    
    def _apply_rl(self, analysis_result: Dict[str, Any], text: str, doc_type: str) -> Dict[str, Any]:
        """
        강화학습(RL) 기반으로 분석 결과를 평가하고 개선합니다.
        
        Args:
            analysis_result: 기존 분석 결과 딕셔너리
            text: 원본 문서 텍스트
            doc_type: 문서 유형
            
        Returns:
            개선된 분석 결과 딕셔너리
        """
        # 분석 결과의 품질 평가 (보상 계산)
        reward, feedback = self._evaluate_analysis_quality(analysis_result, text, doc_type)
        
        logger.info(f"분석 품질 평가 - 보상: {reward:.2f}")
        
        # 보상이 높은 경우 (이미 충분히 좋은 결과)
        if reward >= 0.8:
            analysis_result["rl_feedback"] = "분석 결과가 이미 높은 품질로 평가되어 추가 개선이 필요하지 않습니다."
            analysis_result["rl_reward"] = reward
            return analysis_result
            
        # 피드백을 활용하여 결과 개선
        improved_result = self._improve_analysis_with_feedback(analysis_result, feedback, text, doc_type)
        improved_result["rl_feedback"] = feedback
        improved_result["rl_reward"] = reward
        
        return improved_result
    
    def _evaluate_analysis_quality(self, analysis_result: Dict[str, Any], text: str, doc_type: str) -> Tuple[float, str]:
        """
        분석 결과의 품질을 평가하여 보상 값과 피드백을 생성합니다.
        
        Args:
            analysis_result: 평가할 분석 결과
            text: 원본 문서 텍스트
            doc_type: 문서 유형
            
        Returns:
            (보상 값, 피드백 텍스트) 튜플
        """
        # 평가 항목별 점수 초기화
        scores = {
            "구조_인식": 0.0,
            "논리_일관성": 0.0,
            "근거_기반": 0.0,
            "정보_포괄성": 0.0,
            "실용성": 0.0
        }
        
        # 샘플 텍스트 (너무 긴 텍스트의 경우)
        sample_text = text[:5000] if len(text) > 5000 else text
        
        # LLM을 사용한 분석 품질 평가
        prompt = f"""
        다음은 문서 분석 결과입니다. 이 분석 결과의 품질을 평가하고 각 항목별로 0-10점 사이의 점수를 부여해주세요.
        
        원본 문서 일부:
        {sample_text}
        
        문서 유형: {doc_type}
        
        분석 결과:
        요약: {analysis_result.get('summary', '요약 없음')}
        
        상세 분석: {analysis_result.get('analysis', '분석 없음')}
        
        권장사항: {analysis_result.get('recommendations', '권장사항 없음')}
        
        평가 항목:
        1. 구조 인식 (0-10점): 문서의 구조를 얼마나 잘 파악했는지
        2. 논리 일관성 (0-10점): 분석 과정에서 논리적 모순이 없는지
        3. 근거 기반 (0-10점): 원문 인용 등 근거를 얼마나 제시했는지
        4. 정보 포괄성 (0-10점): 문서의 핵심 정보를 누락없이 포함했는지
        5. 실용성 (0-10점): 제안 사항이 실제로 적용 가능한지
        
        각 항목에 대한 점수와 그 이유를 간략히 설명해주세요.
        또한, 분석 결과를 개선하기 위한 구체적인 피드백을 제공해주세요.
        
        답변 형식:
        구조_인식: [점수]
        논리_일관성: [점수]
        근거_기반: [점수]
        정보_포괄성: [점수]
        실용성: [점수]
        
        개선을_위한_피드백: [피드백]
        """
        
        try:
            response = self._generate_response(prompt)
            
            # 점수 추출 (각 항목별)
            for category in scores.keys():
                pattern = rf"{category}:\s*(\d+)"
                import re
                match = re.search(pattern, response)
                if match:
                    score = int(match.group(1))
                    # 0-10 점수를 0-1 범위로 정규화
                    scores[category] = min(max(score / 10.0, 0.0), 1.0)
            
            # 피드백 추출
            feedback_pattern = r"개선을_위한_피드백:\s*(.*?)(?:\n\n|\Z)"
            feedback_match = re.search(feedback_pattern, response, re.DOTALL)
            feedback = feedback_match.group(1).strip() if feedback_match else "피드백을 추출할 수 없습니다."
            
            # 가중치를 적용한 최종 보상 계산
            weighted_reward = sum(scores[category] * self.reward_weights[category] for category in scores)
            
            return weighted_reward, feedback
            
        except Exception as e:
            logger.error(f"분석 품질 평가 중 오류 발생: {str(e)}")
            return 0.5, f"평가 중 오류 발생: {str(e)}"
    
    def _improve_analysis_with_feedback(self, analysis_result: Dict[str, Any], feedback: str, text: str, doc_type: str) -> Dict[str, Any]:
        """
        피드백을 바탕으로 분석 결과를 개선합니다.
        
        Args:
            analysis_result: 기존 분석 결과
            feedback: 개선을 위한 피드백
            text: 원본 문서 텍스트
            doc_type: 문서 유형
            
        Returns:
            개선된 분석 결과
        """
        # 샘플 텍스트 (너무 긴 텍스트의 경우)
        sample_text = text[:5000] if len(text) > 5000 else text
        
        prompt = f"""
        다음은 문서 분석 결과와 이에 대한 피드백입니다. 피드백을 반영하여 분석 결과를 개선해주세요.
        
        원본 문서 일부:
        {sample_text}
        
        문서 유형: {doc_type}
        
        현재 분석 결과:
        요약: {analysis_result.get('summary', '요약 없음')}
        
        상세 분석: {analysis_result.get('analysis', '분석 없음')}
        
        권장사항: {analysis_result.get('recommendations', '권장사항 없음')}
        
        개선을 위한 피드백:
        {feedback}
        
        위 피드백을 고려하여 분석 결과를 개선해주세요. 특히 피드백에서 지적된 부분을 중점적으로 보완하세요.
        원래 분석 결과의 좋은 부분은 유지하면서, 부족한 부분을 채워주세요.
        
        개선된 분석 결과를 다음 형식으로 제공해주세요:
        1. 요약: 문서의 핵심 내용을 간결하게 요약
        2. 상세 분석: 문서의 주요 내용을 섹션별로 분석
        3. 평가: 문서의 강점과 약점, 논리적 일관성 평가
        4. 제안사항: 개선이나 보완이 필요한 사항
        """
        
        try:
            response = self._generate_response(prompt)
            improved_result = self._extract_sections(response)
            
            # 원본 결과의 일부 필드 유지 (예: 문서 유형, 내부 추론 과정 등)
            for key in analysis_result:
                if key not in improved_result and key not in ["summary", "analysis", "recommendations", "evaluation"]:
                    improved_result[key] = analysis_result[key]
            
            return improved_result
            
        except Exception as e:
            logger.error(f"분석 결과 개선 중 오류 발생: {str(e)}")
            return analysis_result  # 오류 발생 시 원본 결과 반환
    
    def analyze_project(self, text: str, method: str = "standard") -> Dict[str, Any]:
        """
        국책과제 문서를 분석합니다.
        
        Args:
            text: 분석할 문서 텍스트
            method: 분석 방법 ("standard", "cot", "rl", "hybrid" 중 하나)
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 텍스트가 너무 길면 분할
            if len(text) > 30000:
                chunks = self.text_splitter.split_text(text)
                # 처음 몇 개의 청크만 사용 (최대 30,000자)
                text = " ".join(chunks[:5])
            
            # 문서 유형 감지
            doc_type = self._detect_document_type(text)
            logger.info(f"감지된 문서 유형: {doc_type}")
            
            # 분석 방법에 따른 처리
            if method == "cot" or method == "hybrid":
                # Chain-of-Thought 방식 분석
                result = self._cot_analyze_document(text, doc_type, method)
                
                # 하이브리드 방식인 경우 RL 기반 개선 적용
                if method == "hybrid":
                    result = self._apply_rl(result, text, doc_type)
            elif method == "rl":
                # 기본 분석 후 RL 적용
                template = self.templates.get("standard", self.templates["standard"])
                prompt = template.format(text=text)
                response = self._generate_response(prompt)
                
                # 응답 파싱
                result = self._extract_sections(response)
                result["document_type"] = doc_type
                
                # RL 기반 개선 적용
                result = self._apply_rl(result, text, doc_type)
            else:
                # 기존 방식 분석 (표준)
                template = self.templates.get(method, self.templates["standard"])
                prompt = template.format(text=text)
                response = self._generate_response(prompt)
                
                # 응답 파싱
                result = self._extract_sections(response)
                result["document_type"] = doc_type
            
            # 결과가 비어있거나 형식이 올바르지 않은 경우 기본값 설정
            if not result or not isinstance(result, dict):
                result = {
                    "analysis": "분석 결과를 추출할 수 없습니다.",
                    "summary": "요약을 생성할 수 없습니다.",
                    "recommendations": "권장사항을 생성할 수 없습니다.",
                    "document_type": doc_type
                }
            
            return result
            
        except Exception as e:
            logger.error(f"문서 분석 중 오류 발생: {str(e)}")
            return {
                "error": f"분석 중 오류가 발생했습니다: {str(e)}",
                "analysis": "오류로 인해 분석을 완료할 수 없습니다.",
                "summary": "오류로 인해 요약을 생성할 수 없습니다.",
                "recommendations": "오류로 인해 권장사항을 생성할 수 없습니다."
            }
    
    def _combine_chunk_results(self, chunk_results: List[str]) -> str:
        """
        여러 청크의 분석 결과를 통합합니다.
        
        Args:
            chunk_results: 청크별 분석 결과 목록
            
        Returns:
            통합된 분석 결과
        """
        if not chunk_results:
            return ""
        
        # 각 청크의 섹션 추출
        all_sections = [self._extract_sections(result) for result in chunk_results]
        
        # 통합 프롬프트 구성
        prompt = """
        당신은 국책과제 전문가 AI입니다. 다음은 긴 국책과제 문서를 여러 부분으로 나누어 분석한 결과입니다.
        이 분석 결과들을 통합하여 일관되고 포괄적인 최종 분석 결과를 제공해주세요.
        
        분석 결과:
        """
        
        for i, sections in enumerate(all_sections):
            prompt += f"\n\n부분 {i+1}:\n"
            prompt += f"상세 분석: {sections['analysis']}\n"
            prompt += f"요약: {sections['summary']}\n"
            prompt += f"권장사항: {sections['recommendations']}\n"
        
        prompt += """
        위 분석 결과들을 통합하여 다음 형식으로 최종 분석 결과를 제공해주세요:
        1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
        2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
        3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
        
        각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
        중복된 내용은 제거하고, 모순된 내용은 조정하여 일관된 분석 결과를 제공해주세요.
        """
        
        # 통합 분석 수행
        response = self.model.generate_content(prompt)
        return response.text
    
    def analyze_with_feedback(self, text: str, feedback: Optional[str] = None) -> Dict[str, str]:
        """
        이전 분석에 대한 피드백을 반영하여 국책과제 문서를 재분석합니다.
        강화학습(RL) 원리를 적용하여 피드백을 통해 분석 품질을 향상시킵니다.
        
        Args:
            text: 분석할 문서 텍스트
            feedback: 이전 분석에 대한 피드백 (없으면 None)
            
        Returns:
            분석 결과 딕셔너리
        """
        if not text:
            return {"error": "분석할 텍스트가 없습니다."}
        
        if not self.api_key:
            return {"error": "API 키가 설정되지 않았습니다."}
        
        try:
            # 기본 분석 수행
            base_results = self.analyze_project(text, method="hybrid")
            
            # 피드백이 없으면 기본 분석 결과 반환
            if not feedback:
                return base_results
            
            # 피드백을 반영한 재분석 프롬프트 구성
            prompt = f"""
            당신은 국책과제 전문가 AI입니다. 다음은 국책과제 문서에 대한 이전 분석 결과와 그에 대한 피드백입니다.
            피드백을 반영하여 분석 결과를 개선해주세요.
            
            문서 내용:
            {text[:5000]}...  # 문서가 너무 길면 일부만 포함
            
            이전 분석 결과:
            상세 분석: {base_results["analysis"]}
            요약: {base_results["summary"]}
            권장사항: {base_results["recommendations"]}
            
            피드백:
            {feedback}
            
            피드백을 반영하여 다음 형식으로 개선된 분석 결과를 제공해주세요:
            1. 상세 분석: 국책과제의 목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등을 분석합니다.
            2. 요약: 국책과제의 핵심 내용을 간결하게 요약합니다.
            3. 권장사항: 국책과제의 성공적인 수행을 위한 권장사항을 제시합니다.
            
            각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
            """
            
            # 재분석 수행
            response = self.model.generate_content(prompt)
            
            # 섹션 추출
            sections = self._extract_sections(response)
            
            return {
                "analysis": sections["analysis"],
                "summary": sections["summary"],
                "recommendations": sections["recommendations"],
                "feedback_applied": True
            }
            
        except Exception as e:
            return {"error": f"분석 중 오류가 발생했습니다: {str(e)}"}
    
    def extract_key_insights(self, text: str, num_insights: int = 5) -> List[str]:
        """
        국책과제 문서에서 핵심 인사이트를 추출합니다.
        
        Args:
            text: 분석할 문서 텍스트
            num_insights: 추출할 인사이트 수
            
        Returns:
            인사이트 목록
        """
        if not text:
            return []
        
        if not self.api_key:
            return []
        
        try:
            prompt = f"""
            당신은 국책과제 전문가 AI입니다. 다음 국책과제 문서에서 가장 중요한 인사이트 {num_insights}개를 추출해주세요.
            각 인사이트는 국책과제의 성공적인 수행에 중요한 정보여야 합니다.
            
            문서 내용:
            {text[:10000]}...  # 문서가 너무 길면 일부만 포함
            
            인사이트 {num_insights}개를 번호가 매겨진 목록으로 제공해주세요.
            각 인사이트는 한 문장으로 간결하게 작성하되, 충분한 정보를 포함해야 합니다.
            """
            
            response = self.model.generate_content(prompt)
            
            # 인사이트 추출
            insights = []
            for line in response.text.split("\n"):
                line = line.strip()
                if line and (line.startswith("1.") or line.startswith("2.") or 
                            line.startswith("3.") or line.startswith("4.") or 
                            line.startswith("5.") or line.startswith("6.") or 
                            line.startswith("7.") or line.startswith("8.") or 
                            line.startswith("9.") or line.startswith("10.")):
                    # 번호 제거
                    insight = line[line.find(".")+1:].strip()
                    insights.append(insight)
            
            return insights[:num_insights]  # 요청한 수만큼만 반환
            
        except Exception as e:
            return [f"인사이트 추출 중 오류가 발생했습니다: {str(e)}"]
    
    def self_verification(self, text: str, analysis_result: Dict[str, str]) -> Dict[str, str]:
        """
        모델이 생성한 분석 결과를 스스로 검증하는 메서드입니다.
        
        Args:
            text: 원본 텍스트
            analysis_result: 분석 결과
            
        Returns:
            Dict[str, str]: 검증 결과
        """
        logger.info("분석 결과 자체 검증 중...")
        
        # 텍스트가 너무 길면 요약하여 사용
        if len(text) > 10000:
            text_for_verification = text[:10000] + "..."
        else:
            text_for_verification = text
        
        # 검증 프롬프트 구성
        prompt = f"""
        다음은 국책과제 보고서 내용과 이에 대한 분석 결과입니다.
        분석 결과가 정확하고 완전한지 검증해주세요.
        
        ## 보고서 내용 (일부):
        {text_for_verification}
        
        ## 분석 결과:
        분석: {analysis_result.get('analysis', '분석 결과 없음')}
        
        요약: {analysis_result.get('summary', '요약 결과 없음')}
        
        권장사항: {analysis_result.get('recommendations', '권장사항 없음')}
        
        ## 검증 지침:
        1. 분석이 보고서의 핵심 내용을 모두 포함하고 있는지 확인하세요.
        2. 사실 관계에 오류가 있는지 확인하세요.
        3. 논리적 일관성이 있는지 확인하세요.
        4. 개선이 필요한 부분이 있는지 확인하세요.
        
        ## 검증 결과:
        다음 형식으로 검증 결과를 제공해주세요:
        
        1. 정확성 평가 (1-10점):
        2. 완전성 평가 (1-10점):
        3. 논리적 일관성 평가 (1-10점):
        4. 발견된 문제점:
        5. 개선 제안:
        """
        
        # 검증 결과 생성
        verification_response = self._generate_response(prompt)
        
        # 검증 결과 파싱
        verification_result = {
            "verification_response": verification_response,
            "accuracy_score": self._extract_score(verification_response, "정확성"),
            "completeness_score": self._extract_score(verification_response, "완전성"),
            "consistency_score": self._extract_score(verification_response, "논리적 일관성"),
            "issues": self._extract_section(verification_response, "발견된 문제점"),
            "suggestions": self._extract_section(verification_response, "개선 제안")
        }
        
        return verification_result

    def _extract_score(self, text: str, score_type: str) -> int:
        """
        텍스트에서 점수를 추출합니다.
        
        Args:
            text: 검증 결과 텍스트
            score_type: 점수 유형 (예: "정확성")
            
        Returns:
            int: 추출된 점수 (1-10)
        """
        # 점수 패턴 검색
        pattern = f"{score_type} \\(1-10점\\): *(\\d+)"
        match = re.search(pattern, text)
        
        if match:
            score = int(match.group(1))
            # 점수 범위 제한
            return max(1, min(10, score))
        else:
            # 기본값 반환
            return 5

    def improve_with_feedback(self, text: str, analysis_result: Dict[str, str], 
                             verification_result: Dict[str, str]) -> Dict[str, str]:
        """
        검증 결과를 바탕으로 분석 결과를 개선합니다.
        
        Args:
            text: 원본 텍스트
            analysis_result: 분석 결과
            verification_result: 검증 결과
            
        Returns:
            Dict[str, str]: 개선된 분석 결과
        """
        logger.info("피드백을 바탕으로 분석 결과 개선 중...")
        
        # 텍스트가 너무 길면 요약하여 사용
        if len(text) > 5000:
            text_for_improvement = text[:5000] + "..."
        else:
            text_for_improvement = text
        
        # 개선 프롬프트 구성
        prompt = f"""
        다음은 국책과제 보고서 내용, 기존 분석 결과, 그리고 검증 결과입니다.
        검증 결과를 바탕으로 분석 결과를 개선해주세요.
        
        ## 보고서 내용 (일부):
        {text_for_improvement}
        
        ## 기존 분석 결과:
        분석: {analysis_result.get('analysis', '분석 결과 없음')}
        
        요약: {analysis_result.get('summary', '요약 결과 없음')}
        
        권장사항: {analysis_result.get('recommendations', '권장사항 없음')}
        
        ## 검증 결과:
        정확성 점수: {verification_result.get('accuracy_score', 5)}/10
        완전성 점수: {verification_result.get('completeness_score', 5)}/10
        논리적 일관성 점수: {verification_result.get('consistency_score', 5)}/10
        
        발견된 문제점: {verification_result.get('issues', '문제점 없음')}
        
        개선 제안: {verification_result.get('suggestions', '개선 제안 없음')}
        
        ## 개선 지침:
        1. 검증 결과에서 지적된 문제점을 해결하세요.
        2. 개선 제안을 반영하여 분석 결과를 향상시키세요.
        3. 보고서 내용에 더 충실하게 분석하세요.
        4. 논리적 일관성을 유지하세요.
        
        ## 개선된 분석 결과:
        다음 형식으로 개선된 분석 결과를 제공해주세요:
        
        ### 분석:
        (개선된 분석 내용)
        
        ### 요약:
        (개선된 요약 내용)
        
        ### 권장사항:
        (개선된 권장사항 내용)
        """
        
        # 개선된 분석 결과 생성
        improved_response = self._generate_response(prompt)
        
        # 개선된 분석 결과 파싱
        improved_analysis = self._extract_section(improved_response, "분석")
        improved_summary = self._extract_section(improved_response, "요약")
        improved_recommendations = self._extract_section(improved_response, "권장사항")
        
        # 개선된 결과가 없으면 기존 결과 유지
        improved_result = {
            "analysis": improved_analysis if improved_analysis else analysis_result.get("analysis", ""),
            "summary": improved_summary if improved_summary else analysis_result.get("summary", ""),
            "recommendations": improved_recommendations if improved_recommendations else analysis_result.get("recommendations", ""),
            "improvement_applied": True
        }
        
        return improved_result

    def save_analysis_history(self, analysis_result: Dict[str, Any], user_feedback: Optional[Dict[str, Any]] = None) -> str:
        """
        분석 결과와 사용자 피드백을 저장합니다.
        
        Args:
            analysis_result: 분석 결과 딕셔너리
            user_feedback: 사용자 피드백 (선택적)
            
        Returns:
            저장된 파일 경로
        """
        try:
            # 현재 시간을 파일명에 사용
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_type = analysis_result.get("document_type", "unknown")
            
            # 저장할 데이터 구성
            data_to_save = {
                "timestamp": timestamp,
                "document_type": doc_type,
                "analysis_result": analysis_result
            }
            
            # 사용자 피드백이 있는 경우 추가
            if user_feedback:
                data_to_save["user_feedback"] = user_feedback
            
            # 파일 경로 생성
            file_path = os.path.join(self.analysis_history_dir, f"analysis_{doc_type}_{timestamp}.json")
            
            # JSON 파일로 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
            logger.info(f"분석 이력이 저장되었습니다: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"분석 이력 저장 중 오류 발생: {str(e)}")
            return f"저장 실패: {str(e)}"
    
    def record_user_feedback(self, analysis_id: str, feedback: Dict[str, Any]) -> bool:
        """
        사용자 피드백을 분석 이력에 추가합니다.
        
        Args:
            analysis_id: 분석 ID (파일명 또는 전체 경로)
            feedback: 사용자 피드백 (점수, 코멘트 등)
            
        Returns:
            성공 여부
        """
        try:
            # 파일 이름에서 경로 분리
            if os.path.dirname(analysis_id):
                file_path = analysis_id
            else:
                file_path = os.path.join(self.analysis_history_dir, analysis_id)
                
            # 확장자가 없으면 .json 추가
            if not file_path.endswith('.json'):
                file_path += '.json'
                
            # 파일이 존재하는지 확인
            if not os.path.exists(file_path):
                logger.error(f"분석 파일을 찾을 수 없습니다: {file_path}")
                return False
                
            # 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 피드백 추가 또는 업데이트
            if "user_feedback" in data:
                # 기존 피드백에 새 피드백 병합
                data["user_feedback"].update(feedback)
            else:
                data["user_feedback"] = feedback
                
            # 피드백 시간 추가
            data["user_feedback"]["feedback_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            # 다시 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"사용자 피드백이 기록되었습니다: {file_path}")
            
            # 피드백 데이터를 RL 학습에 활용
            self._update_rl_weights_from_feedback(feedback)
            
            return True
            
        except Exception as e:
            logger.error(f"사용자 피드백 기록 중 오류 발생: {str(e)}")
            return False
            
    def _update_rl_weights_from_feedback(self, feedback: Dict[str, Any]) -> None:
        """
        사용자 피드백을 바탕으로 RL 보상 가중치를 업데이트합니다.
        
        Args:
            feedback: 사용자 피드백
        """
        try:
            # 피드백에 평가 항목 점수가 있는 경우 (5점 만점)
            if "ratings" in feedback and isinstance(feedback["ratings"], dict):
                ratings = feedback["ratings"]
                
                # 모든 항목의 평균 점수 계산
                avg_score = sum(ratings.values()) / len(ratings)
                
                # 평균보다 낮은 항목의 가중치 증가, 높은 항목의 가중치 감소
                for category, score in ratings.items():
                    if category in self.reward_weights:
                        # 점수 정규화 (0-5 -> -0.1 ~ 0.1)
                        adjustment = (score - avg_score) / 50.0
                        
                        # 가중치 조정 (최대 ±10%)
                        self.reward_weights[category] = max(0.05, min(0.5, self.reward_weights[category] - adjustment))
                
                # 가중치 합이 1이 되도록 정규화
                weight_sum = sum(self.reward_weights.values())
                for category in self.reward_weights:
                    self.reward_weights[category] /= weight_sum
                    
                logger.info(f"RL 가중치가 사용자 피드백에 따라 업데이트되었습니다: {self.reward_weights}")
                
        except Exception as e:
            logger.error(f"RL 가중치 업데이트 중 오류 발생: {str(e)}")

    def generate_learning_dataset(self, min_user_score: float = 4.0) -> List[Dict[str, Any]]:
        """
        사용자 피드백 데이터 중 우수 사례를 학습 데이터셋으로 생성합니다.
        
        Args:
            min_user_score: 학습에 포함할 최소 사용자 평점 (5점 만점)
            
        Returns:
            학습 데이터셋 (프롬프트-응답 쌍 목록)
        """
        dataset = []
        
        try:
            # 분석 이력 파일 목록 가져오기
            history_files = [f for f in os.listdir(self.analysis_history_dir) if f.endswith('.json')]
            
            for file_name in history_files:
                file_path = os.path.join(self.analysis_history_dir, file_name)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 사용자 피드백이 있고, 평점이 기준 이상인 경우만 포함
                    if "user_feedback" in data and "overall_rating" in data["user_feedback"]:
                        overall_rating = float(data["user_feedback"]["overall_rating"])
                        
                        if overall_rating >= min_user_score:
                            # 학습 데이터 생성
                            analysis_result = data["analysis_result"]
                            document_type = data.get("document_type", "unknown")
                            
                            # CoT 분석 내부 추론 과정 추출
                            thinking_process = analysis_result.get("thinking_process", "")
                            
                            # 프롬프트 생성 (원본 문서 텍스트가 없어서 대체 텍스트 사용)
                            prompt = f"다음 {document_type} 문서를 분석해주세요: [문서 내용]"
                            
                            # 응답 생성
                            response = f"<think>\n{thinking_process}\n</think>\n\n"
                            response += f"요약: {analysis_result.get('summary', '')}\n\n"
                            response += f"상세 분석: {analysis_result.get('analysis', '')}\n\n"
                            response += f"권장사항: {analysis_result.get('recommendations', '')}"
                            
                            dataset.append({
                                "prompt": prompt,
                                "response": response,
                                "document_type": document_type,
                                "user_rating": overall_rating
                            })
                
                except Exception as e:
                    logger.error(f"파일 처리 중 오류 발생: {file_name}, {str(e)}")
                    continue
            
            logger.info(f"학습 데이터셋 생성 완료: {len(dataset)}개 항목")
            return dataset
            
        except Exception as e:
            logger.error(f"학습 데이터셋 생성 중 오류 발생: {str(e)}")
            return []
    
    def analyze_project_with_verification(self, text: str, method: str = "hybrid", 
                                         verification_rounds: int = 1) -> Dict[str, str]:
        """
        국책과제 보고서를 분석하고 자체 검증 및 개선 과정을 거칩니다.
        
        Args:
            text: 분석할 텍스트
            method: 분석 방법 ("standard", "cot", "rl", "hybrid" 중 하나)
            verification_rounds: 검증 및 개선 반복 횟수
            
        Returns:
            Dict[str, str]: 분석 결과
        """
        logger.info(f"국책과제 분석 시작 (방법: {method}, 검증 라운드: {verification_rounds})")
        
        # 초기 분석 수행
        result = self.analyze_project(text, method)
        
        # 검증 및 개선 반복
        for i in range(verification_rounds):
            logger.info(f"검증 라운드 {i+1}/{verification_rounds} 시작")
            
            # 결과 자체 검증
            logger.info("분석 결과 자체 검증 중...")
            verification_result = self.self_verification(text, result)
            
            # 검증 점수 추출
            relevance_score = self._extract_score(verification_result.get("relevance_verification", ""), "관련성")
            accuracy_score = self._extract_score(verification_result.get("accuracy_verification", ""), "정확성")
            completeness_score = self._extract_score(verification_result.get("completeness_verification", ""), "완전성")
            usefulness_score = self._extract_score(verification_result.get("usefulness_verification", ""), "유용성")
            
            # 점수 평균 계산
            scores = [s for s in [relevance_score, accuracy_score, completeness_score, usefulness_score] if s > 0]
            avg_score = sum(scores) / len(scores) if scores else 0
            logger.info(f"검증 평균 점수: {avg_score:.2f}/10")
            
            # 점수가 높으면 더 이상 개선하지 않음
            if avg_score >= 8.5:
                logger.info(f"검증 점수가 충분히 높음 (평균: {avg_score:.2f}/10). 개선 과정 생략.")
                break
                
            # 피드백을 바탕으로 개선
            logger.info("피드백을 바탕으로 분석 결과 개선 중...")
            result = self.improve_with_feedback(text, result, verification_result)
        
        # 분석 이력 저장
        self.save_analysis_history(result)
            
        return result

    def export_to_pdf(self, analysis_result: Dict[str, Any], output_path: str = None) -> str:
        """분석 결과를 PDF로 내보냅니다."""
        if not PDF_SUPPORT:
            logger.warning("PDF 내보내기가 지원되지 않습니다.")
            return ""
        
        if output_path is None:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                output_path = temp_file.name
        
        # PDF 생성
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # 한글 스타일 추가
        try:
            if os.name == 'nt':  # 윈도우
                styles.add(ParagraphStyle(
                    name='Korean',
                    fontName='Malgun',
                    fontSize=10,
                    leading=12
                ))
                styles.add(ParagraphStyle(
                    name='KoreanTitle',
                    fontName='Malgun',
                    fontSize=16,
                    leading=20,
                    alignment=1  # 중앙 정렬
                ))
                styles.add(ParagraphStyle(
                    name='KoreanHeading',
                    fontName='Malgun',
                    fontSize=14,
                    leading=16,
                    spaceAfter=10
                ))
            else:  # 리눅스
                # 폰트가 등록되었는지 확인
                korean_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
                
                styles.add(ParagraphStyle(
                    name='Korean',
                    fontName=korean_font,
                    fontSize=10,
                    leading=12
                ))
                styles.add(ParagraphStyle(
                    name='KoreanTitle',
                    fontName=korean_font,
                    fontSize=16,
                    leading=20,
                    alignment=1  # 중앙 정렬
                ))
                styles.add(ParagraphStyle(
                    name='KoreanHeading',
                    fontName=korean_font,
                    fontSize=14,
                    leading=16,
                    spaceAfter=10
                ))
        except Exception as e:
            logger.warning(f"한글 스타일 추가 실패: {str(e)}. 기본 스타일을 사용합니다.")
            # 기본 스타일 사용
            styles.add(ParagraphStyle(
                name='Korean',
                fontName='Helvetica',
                fontSize=10,
                leading=12
            ))
            styles.add(ParagraphStyle(
                name='KoreanTitle',
                fontName='Helvetica-Bold',
                fontSize=16,
                leading=20,
                alignment=1  # 중앙 정렬
            ))
            styles.add(ParagraphStyle(
                name='KoreanHeading',
                fontName='Helvetica-Bold',
                fontSize=14,
                leading=16,
                spaceAfter=10
            ))

        # PDF에 들어갈 요소 목록
        elements = []
        
        # 제목 추가
        doc_type = analysis_result.get("document_type", "문서")
        title = f"{doc_type} 분석 보고서"
        elements.append(Paragraph(title, styles["KoreanTitle"]))
        elements.append(Spacer(1, 12))
        
        # 분석 날짜 추가
        now = datetime.now().strftime("%Y년 %m월 %d일")
        elements.append(Paragraph(f"분석 일자: {now}", styles["Korean"]))
        elements.append(Spacer(1, 24))
        
        # 문서 유형 정보
        elements.append(Paragraph("문서 유형: " + doc_type, styles["Korean"]))
        elements.append(Spacer(1, 12))
        
        # 요약 섹션
        elements.append(Paragraph("요약", styles["KoreanHeading"]))
        summary = analysis_result.get('summary', "요약을 찾을 수 없습니다.")
        elements.append(Paragraph(summary, styles["Korean"]))
        elements.append(Spacer(1, 12))
        
        # 상세 분석 섹션
        elements.append(Paragraph("상세 분석", styles["KoreanHeading"]))
        analysis = analysis_result.get('analysis', "분석 결과를 찾을 수 없습니다.")
        # 마크다운 형식의 볼드체 처리
        analysis = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', analysis)
        analysis = re.sub(r'\*(.*?)\*', r'<i>\1</i>', analysis)
        
        # 단락 나누기
        paragraphs = analysis.split('\n\n')
        for para in paragraphs:
            if para.strip():
                elements.append(Paragraph(para, styles["Korean"]))
                elements.append(Spacer(1, 6))
        
        elements.append(Spacer(1, 12))
        
        # 권장사항 섹션
        elements.append(Paragraph("권장사항", styles["KoreanHeading"]))
        recommendations = analysis_result.get('recommendations', "권장사항을 찾을 수 없습니다.")
        recommendations = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', recommendations)
        
        # 단락 나누기
        rec_paragraphs = recommendations.split('\n\n')
        for para in rec_paragraphs:
            if para.strip():
                elements.append(Paragraph(para, styles["Korean"]))
                elements.append(Spacer(1, 6))
        
        # 평가 정보 (있는 경우)
        if "evaluation" in analysis_result:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("평가", styles["KoreanHeading"]))
            evaluation = analysis_result.get("evaluation", "평가 정보를 찾을 수 없습니다.")
            elements.append(Paragraph(evaluation, styles["Korean"]))
        
        # PDF 생성
        doc.build(elements)
        
        logger.info(f"PDF 보고서가 생성되었습니다: {output_path}")
        return output_path