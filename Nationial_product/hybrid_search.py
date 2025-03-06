import os
import json
import requests
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable
import google.generativeai as genai
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
from functools import lru_cache
import threading
import concurrent.futures
from dataclasses import dataclass, field

# 캐싱 관련 상수 정의
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
CACHE_EXPIRY = 24 * 60 * 60  # 24시간(초 단위)
MAX_CACHE_ENTRIES = 1000  # 최대 캐시 항목 수

# 성능 측정을 위한 메트릭 클래스
class PerformanceMetrics:
    """성능 지표를 기록하고 모니터링하는 클래스"""
    
    def __init__(self):
        self.api_calls = {
            "gemini": {"count": 0, "total_time": 0, "errors": 0},
            "perplexity": {"count": 0, "total_time": 0, "errors": 0}
        }
        self.cache_hits = 0
        self.cache_misses = 0
        self.lock = threading.Lock()
    
    def record_api_call(self, api_name: str, duration: float, success: bool):
        """API 호출 지표 기록"""
        with self.lock:
            self.api_calls[api_name]["count"] += 1
            self.api_calls[api_name]["total_time"] += duration
            if not success:
                self.api_calls[api_name]["errors"] += 1
    
    def record_cache_access(self, hit: bool):
        """캐시 접근 지표 기록"""
        with self.lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """성능 지표 요약 반환"""
        with self.lock:
            gemini_avg = self.api_calls["gemini"]["total_time"] / max(1, self.api_calls["gemini"]["count"])
            perplexity_avg = self.api_calls["perplexity"]["total_time"] / max(1, self.api_calls["perplexity"]["count"])
            
            cache_total = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / max(1, cache_total)) * 100
            
            return {
                "api_calls": {
                    "gemini": {
                        "count": self.api_calls["gemini"]["count"],
                        "avg_time": round(gemini_avg, 2),
                        "error_rate": round((self.api_calls["gemini"]["errors"] / max(1, self.api_calls["gemini"]["count"])) * 100, 2)
                    },
                    "perplexity": {
                        "count": self.api_calls["perplexity"]["count"],
                        "avg_time": round(perplexity_avg, 2),
                        "error_rate": round((self.api_calls["perplexity"]["errors"] / max(1, self.api_calls["perplexity"]["count"])) * 100, 2)
                    }
                },
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": round(cache_hit_rate, 2)
                }
            }

# 캐시 관리 클래스
class CacheManager:
    """API 응답 캐싱을 관리하는 클래스"""
    
    def __init__(self, metrics: PerformanceMetrics):
        self.metrics = metrics
        
        # 캐시 디렉토리 생성
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
            
        # 캐시 정리 (오래된 항목 제거)
        self._cleanup_cache()
    
    def _get_cache_key(self, prefix: str, data: str) -> str:
        """캐시 키 생성"""
        hash_object = hashlib.md5(data.encode())
        return f"{prefix}_{hash_object.hexdigest()}"
    
    def _get_cache_path(self, cache_key: str) -> str:
        """캐시 파일 경로 생성"""
        return os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    def get(self, prefix: str, data: str) -> Optional[Dict[str, Any]]:
        """캐시에서 데이터 조회"""
        cache_key = self._get_cache_key(prefix, data)
        cache_path = self._get_cache_path(cache_key)
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 만료 시간 확인
                if cache_data.get("expiry", 0) > time.time():
                    self.metrics.record_cache_access(hit=True)
                    return cache_data.get("data")
            except Exception as e:
                logging.error(f"캐시 읽기 오류: {str(e)}")
        
        self.metrics.record_cache_access(hit=False)
        return None
    
    def set(self, prefix: str, data: str, result: Dict[str, Any]):
        """데이터를 캐시에 저장"""
        cache_key = self._get_cache_key(prefix, data)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cache_data = {
                "expiry": time.time() + CACHE_EXPIRY,
                "data": result
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False)
        except Exception as e:
            logging.error(f"캐시 쓰기 오류: {str(e)}")
    
    def _cleanup_cache(self):
        """오래된 캐시 파일 정리"""
        try:
            cache_files = os.listdir(CACHE_DIR)
            
            # 만료된 파일 제거
            current_time = time.time()
            for filename in cache_files:
                file_path = os.path.join(CACHE_DIR, filename)
                
                try:
                    # 파일 수정 시간 확인
                    mod_time = os.path.getmtime(file_path)
                    if current_time - mod_time > CACHE_EXPIRY:
                        os.remove(file_path)
                except Exception:
                    continue
            
            # 캐시 항목 수 제한
            cache_files = os.listdir(CACHE_DIR)
            if len(cache_files) > MAX_CACHE_ENTRIES:
                # 수정 시간 기준으로 정렬
                cache_files = sorted(cache_files, key=lambda x: os.path.getmtime(os.path.join(CACHE_DIR, x)))
                
                # 가장 오래된 파일부터 삭제
                for filename in cache_files[:len(cache_files) - MAX_CACHE_ENTRIES]:
                    try:
                        os.remove(os.path.join(CACHE_DIR, filename))
                    except Exception:
                        continue
        except Exception as e:
            logging.error(f"캐시 정리 중 오류 발생: {str(e)}")

class KoreanTextProcessor:
    """
    한국어 텍스트 처리 최적화 클래스
    한국어 텍스트의 특성을 고려한 전처리, 정제, 분석 기능을 제공합니다.
    
    지원하는 문서 유형:
    - 국책과제: 정부 지원 사업, 연구개발 계획, 예산 및 성과 관련 문서
    - 법률: 법률문서, 계약서, 판결문 등 법적 문서
    - 논문: 학술 논문, 연구 보고서 등 학술 문서
    """
    
    # 한국어 불용어 목록 (예시)
    STOPWORDS = [
        "이", "그", "저", "것", "및", "에", "의", "을", "를", "이", "가", "은", "는", 
        "등", "에서", "으로", "로", "에게", "뿐", "만", "와", "과", "도", "에도", "까지"
    ]
    
    # 문서 타입별 주요 용어 사전
    DOMAIN_TERMS = {
        # 국책과제 관련 용어
        "연구개발": ["R&D", "연구개발사업", "기술개발", "연구", "개발", "혁신"],
        "정부지원": ["정부과제", "국고지원", "재정지원", "예산지원", "지원사업", "국가지원"],
        "사업화": ["상용화", "기술이전", "사업화지원", "창업", "산업화", "실용화"],
        "기술분야": ["정보통신", "바이오", "에너지", "소재", "기계", "로봇", "환경", "건설", "의료"],
        "평가": ["중간평가", "최종평가", "성과평가", "진도점검", "성과지표", "효과성"],
        "추진체계": ["추진", "계획", "진행", "목표", "과제", "사업", "전략", "로드맵"],
        
        # 법률 관련 용어
        "법령": ["법률", "법규", "시행령", "시행규칙", "조례", "규정", "제도"],
        "계약": ["계약서", "약관", "조항", "합의", "특약", "부칙", "계약조건"],
        "소송": ["소장", "법원", "판결", "원고", "피고", "변론", "항소", "상고", "판례"],
        "권리의무": ["권리", "의무", "책임", "손해배상", "이행", "불이행", "효력", "효과"],
        "법적절차": ["절차", "소송", "재판", "소제기", "청구", "신청", "항고"],
        
        # 논문 관련 용어
        "연구방법": ["방법론", "실험", "조사", "분석", "연구설계", "데이터수집", "검증"],
        "연구결과": ["결과", "발견", "분석결과", "데이터", "통계", "유의미", "경향"],
        "학술용어": ["이론", "패러다임", "개념", "모델", "가설", "변수", "요인", "상관관계"],
        "논문구조": ["초록", "서론", "본론", "결론", "참고문헌", "인용", "각주"],
        "연구목적": ["목적", "의의", "필요성", "배경", "선행연구", "연구질문"]
    }
    
    # 문서 유형별 식별자
    DOCUMENT_TYPE_IDENTIFIERS = {
        "법률": ["제", "조", "항", "호", "법률", "계약", "조항", "법원", "판결", "원고", "피고"],
        "논문": ["초록", "서론", "방법", "결과", "고찰", "결론", "참고문헌", "연구", "가설"],
        "국책과제": ["사업", "계획", "목표", "예산", "추진", "성과", "지원", "과제", "평가"]
    }
    
    @staticmethod
    def clean_text(text: str) -> str:
        """텍스트 정제"""
        import re
        
        # 불필요한 공백, 특수문자 정리
        text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
        text = re.sub(r'[\u3000\xa0]', ' ', text)  # 특수 공백문자 변환
        
        # 특수문자 처리 (괄호 내용 보존)
        text = re.sub(r'[^\w\s\(\)\[\]\{\}가-힣]+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def extract_korean_terms(text: str, min_length: int = 2) -> List[str]:
        """한국어 용어 추출"""
        import re
        
        # 한글 용어 추출 (2글자 이상)
        terms = re.findall(r'[가-힣]{%d,}' % min_length, text)
        
        # 불용어 제거
        terms = [term for term in terms if term not in KoreanTextProcessor.STOPWORDS]
        
        return terms
    
    @staticmethod
    def extract_noun_phrases(text: str) -> List[str]:
        """명사구 추출 (기본 구현)"""
        import re
        
        # 문서 유형별 패턴 정의
        patterns = {
            # 국책과제 관련 패턴
            "국책과제": [
                r'[가-힣]{1,6}\s?[가-힣]{1,6}\s?(사업|정책|제도|기술|산업|과제|전략|계획)',
                r'[가-힣]{2,6}\s?(중장기|단기)\s?[가-힣]{2,6}',
                r'[가-힣]{2,6}\s?(지원금|보조금|융자|출연금|예산)',
                r'[0-9]+\s?차\s?[가-힣]{2,8}\s?(산업|혁명|기술|정책)',
                r'[가-힣]{2,6}\s?(연구개발|기술개발)\s?[가-힣]{2,6}',
                r'[가-힣]{2,6}\s?(성과|목표|과제)\s?[가-힣]{1,6}',
            ],
            
            # 법률 관련 패턴
            "법률": [
                r'제\s?[0-9]+\s?조(\s?\([가-힣0-9]+\))?',
                r'[가-힣]{2,6}\s?(법률|법규|법원|조항|계약|판결)',
                r'[가-힣]{2,6}\s?(소송|재판|판례|권리|의무|책임)',
                r'[가-힣]{1,6}\s?(법률|법원|재판부|판사)\s?[가-힣]{1,6}',
                r'[가-힣]+\s?대\s?[가-힣]+\s?(소송|판결|사건)'
            ],
            
            # 논문 관련 패턴
            "논문": [
                r'[가-힣]{2,6}\s?(연구|실험|조사|분석|검증|결과)',
                r'[가-힣]{2,6}\s?(이론|모델|가설|개념|변수)',
                r'[가-힣]{1,6}\s?(논문|연구|저자|학술지)\s?[가-힣]{1,6}',
                r'[가-힣]{2,6}\s?(통계|데이터|샘플|유의미|상관관계)',
                r'[가-힣]{2,6}\s?(서론|본론|결론|고찰|참고문헌)'
            ]
        }
        
        # 모든 패턴 통합
        all_patterns = []
        for doc_type, pattern_list in patterns.items():
            all_patterns.extend(pattern_list)
        
        results = []
        for pattern in all_patterns:
            matches = re.findall(pattern, text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = ''.join(match)
                    results.append(match)
        
        return results
    
    @staticmethod
    def detect_document_type(text: str) -> str:
        """문서 유형 감지"""
        # 문서에 포함된 식별자 수 계산
        type_scores = {}
        
        for doc_type, identifiers in KoreanTextProcessor.DOCUMENT_TYPE_IDENTIFIERS.items():
            score = 0
            for identifier in identifiers:
                # 대소문자 구분 없이 검색
                score += text.count(identifier)
            type_scores[doc_type] = score
        
        # 가장 높은 점수의 문서 유형 반환
        if not type_scores or max(type_scores.values()) == 0:
            return "국책과제"  # 기본값으로 국책과제 설정
        
        return max(type_scores.items(), key=lambda x: x[1])[0]
    
    @staticmethod
    def map_to_domain_terms(terms: List[str]) -> Dict[str, List[str]]:
        """추출 용어를 도메인 용어로 매핑"""
        result = {}
        
        for category, synonyms in KoreanTextProcessor.DOMAIN_TERMS.items():
            matched = []
            for term in terms:
                if term in synonyms or any(syn in term for syn in synonyms):
                    matched.append(term)
            
            if matched:
                result[category] = matched
        
        return result
    
    @staticmethod
    def analyze_text_structure(text: str) -> Dict[str, Any]:
        """텍스트 구조 분석"""
        import re
        
        # 기본 문서 정보
        lines = text.split('\n')
        paragraphs = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
        
        # 제목 후보 추출
        title_candidates = []
        for line in lines[:10]:  # 처음 10줄에서 제목 찾기
            line = line.strip()
            if 2 < len(line) < 50 and not line.endswith('.'):
                title_candidates.append(line)
        
        # 섹션 구분 패턴 찾기
        section_headers = []
        section_pattern = r'^(\d+\.|\d+\.\d+|[IVXLCDM]+\.|[가-힣]\.)\s+[가-힣].{2,50}$'
        for line in lines:
            line = line.strip()
            if re.match(section_pattern, line, re.MULTILINE):
                section_headers.append(line)
        
        # 표/그림 참조 찾기
        figure_refs = re.findall(r'(그림|표|도표)\s+\d+', text)
        
        return {
            "length": len(text),
            "line_count": len(lines),
            "paragraph_count": len(paragraphs),
            "title_candidates": title_candidates[:3],
            "section_count": len(section_headers),
            "section_headers": section_headers[:5],
            "has_figures": len(figure_refs) > 0,
            "figure_ref_count": len(figure_refs)
        }

class HybridSearchEngine:
    """
    하이브리드 검색 엔진 클래스
    Gemini API와 Perplexity API를 함께 활용하여 더 정확하고 최신 정보를 포함한 분석 결과를 제공합니다.
    
    성능 최적화 기능:
    - API 호출 캐싱으로 중복 요청 최소화
    - 병렬 처리를 통한 응답 시간 단축
    - 성능 메트릭 수집 및 모니터링
    - 적응형 타임아웃 및 재시도 로직
    - 한국어 자연어 처리 최적화
    - 국책과제 도메인 특화 분석
    """
    
    def __init__(self, gemini_api_key: str, perplexity_api_key: str):
        """
        하이브리드 검색 엔진 초기화
        
        Args:
            gemini_api_key: Google Gemini API 키
            perplexity_api_key: Perplexity API 키
        """
        self.gemini_api_key = gemini_api_key
        self.perplexity_api_key = perplexity_api_key
        
        # 성능 메트릭 인스턴스 생성
        self.metrics = PerformanceMetrics()
        
        # 캐시 관리자 인스턴스 생성
        self.cache_manager = CacheManager(self.metrics)
        
        # Gemini 모델 설정
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel(
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
        
        # 로거 설정
        self.logger = logging.getLogger('hybrid_search')
        
        # API 호출 제한 및 설정
        self.api_rate_limits = {
            "gemini": {"calls_per_minute": 60, "last_call_time": 0, "lock": threading.Lock()},
            "perplexity": {"calls_per_minute": 20, "last_call_time": 0, "lock": threading.Lock()}
        }
        
        # 스레드 풀 생성
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    
    def _respect_rate_limit(self, api_name: str):
        """API 호출 속도 제한 준수"""
        with self.api_rate_limits[api_name]["lock"]:
            min_interval = 60 / self.api_rate_limits[api_name]["calls_per_minute"]
            last_call = self.api_rate_limits[api_name]["last_call_time"]
            
            current_time = time.time()
            elapsed = current_time - last_call
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            self.api_rate_limits[api_name]["last_call_time"] = time.time()
    
    def _call_gemini_with_metrics(self, prompt: str) -> Tuple[Any, float]:
        """Gemini API 호출 및 성능 측정"""
        self._respect_rate_limit("gemini")
        
        # 캐시 확인
        cache_data = self.cache_manager.get("gemini", prompt)
        if cache_data:
            return cache_data, 0
        
        start_time = time.time()
        success = False
        
        try:
            response = self.gemini_model.generate_content(prompt)
            success = True
            
            # 결과 캐싱
            self.cache_manager.set("gemini", prompt, response.text)
            
            return response.text, time.time() - start_time
        except Exception as e:
            self.logger.error(f"Gemini API 호출 오류: {str(e)}")
            raise
        finally:
            duration = time.time() - start_time
            self.metrics.record_api_call("gemini", duration, success)
    
    def _call_perplexity_with_metrics(self, data: Dict[str, Any], timeout: int = 40) -> Tuple[Any, float]:
        """Perplexity API 호출 및 성능 측정"""
        self._respect_rate_limit("perplexity")
        
        # 캐시 키용 데이터 문자열 생성
        data_str = json.dumps(data, sort_keys=True)
        
        # 캐시 확인
        cache_data = self.cache_manager.get("perplexity", data_str)
        if cache_data:
            return cache_data, 0
        
        start_time = time.time()
        success = False
        
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Perplexity API 요청 시도 {attempt + 1}/{max_retries}")
                
                response = requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    success = True
                    
                    # 결과 캐싱
                    self.cache_manager.set("perplexity", data_str, content)
                    
                    return content, time.time() - start_time
                
                elif response.status_code == 429:
                    # 속도 제한 - 대기 후 재시도
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # 지수 백오프
                        time.sleep(wait_time)
                        continue
                
                response.raise_for_status()
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise
        
        raise Exception(f"Perplexity API 호출 실패 ({max_retries}회 시도)")
    
    def extract_key_terms(self, text: str) -> List[str]:
        """
        텍스트에서 검색에 사용할 핵심 용어를 추출합니다.
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            핵심 용어 목록
        """
        # 입력 텍스트가 너무 길면 축소
        if len(text) > 15000:
            chunks = self.text_splitter.split_text(text)
            text = chunks[0]  # 첫 번째 청크만 사용
        
        prompt = f"""
        다음 텍스트에서 국책과제와 관련된 핵심 용어를 최대 5개 추출해주세요.
        각 용어는 검색에 사용될 것이므로 구체적이고 관련성이 높아야 합니다.
        용어만 쉼표로 구분하여 나열해주세요.
        
        텍스트:
        {text}
        
        핵심 용어(쉼표로 구분):
        """
        
        try:
            content, _ = self._call_gemini_with_metrics(prompt)
            
            if isinstance(content, str):
                key_terms = content.strip().split(',')
            else:
                key_terms = content.text.strip().split(',')
                
            return [term.strip() for term in key_terms if term.strip()]
        except Exception as e:
            self.logger.error(f"핵심 용어 추출 중 오류 발생: {str(e)}")
            # 오류 발생 시 기본 키워드 반환
            return ["국책과제", "연구개발", "정부지원", "기술혁신"]
    
    def search_web(self, key_terms: List[str]) -> str:
        """
        Perplexity API를 사용하여 웹 검색을 수행합니다.
        
        Args:
            key_terms: 검색할 핵심 용어 목록
            
        Returns:
            검색 결과 텍스트
        """
        logger = logging.getLogger('perplexity_api')
        
        if not self.perplexity_api_key:
            return "Perplexity API 키가 설정되지 않았습니다."
        
        search_query = " ".join(key_terms) + " 국책과제 최신 동향 정책"
        
        data = {
            "model": "sonar",  # 웹 검색 가능한 최신 모델로 변경
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that provides accurate information about Korean government projects, policies, and trends."},
                {"role": "user", "content": f"다음 주제에 대한 최신 정보를 검색해주세요: {search_query}. 국책과제와 관련된 최신 정책, 동향, 지원 사항 등을 중심으로 검색하고, 검색 결과를 요약해주세요."}
            ],
            "max_tokens": 4000,
            "temperature": 0.2,
            "stream": False
        }
        
        try:
            content, _ = self._call_perplexity_with_metrics(data)
            return content
        except Exception as e:
            logger.error(f"웹 검색 중 오류 발생: {str(e)}")
            
            # 오류 발생 시 Gemini 모델로 대체
            try:
                logger.info("Perplexity API 연결 실패, Gemini 모델로 대체 정보 생성")
                prompt = f"""
                다음 주제에 대한 정보를 제공해주세요: {search_query}
                
                비록 실시간 웹 검색은 수행할 수 없지만, 국책과제 관련 일반적인 정보와 동향에 대해 알려주세요.
                최근 정책 방향, 지원 프로그램, 자금 지원 메커니즘, 국책과제 신청 및 평가 과정에 대한 
                일반적인 정보를 포함해주세요.
                """
                
                content, _ = self._call_gemini_with_metrics(prompt)
                return f"[참고: 실시간 웹 검색을 이용할 수 없어 일반적인 정보를 제공합니다]\n\n{content}"
            
            except Exception as fallback_error:
                logger.error(f"대체 정보 생성 중 오류 발생: {str(fallback_error)}")
                return "웹 검색 및 대체 정보 생성에 모두 실패했습니다. 나중에 다시 시도해주세요."
    
    def enhance_analysis(self, original_analysis: str, web_results: str) -> str:
        """
        원본 분석 결과와 웹 검색 결과를 통합하여 향상된 분석 결과를 생성합니다.
        
        Args:
            original_analysis: 원본 분석 결과
            web_results: 웹 검색 결과
            
        Returns:
            향상된 분석 결과
        """
        prompt = f"""
        당신은 국책과제 전문가 AI입니다. 다음 두 가지 정보를 통합하여 더 정확하고 최신 정보를 포함한 분석 결과를 생성해주세요.
        
        1. 원본 분석 결과:
        {original_analysis}
        
        2. 웹 검색 결과 (최신 정보):
        {web_results}
        
        다음 지침에 따라 통합된 분석 결과를 생성해주세요:
        1. 원본 분석의 주요 내용을 유지하면서 최신 정보로 보완하세요.
        2. 웹 검색 결과에서 발견된 새로운 정책, 동향, 지원 사항 등을 추가하세요.
        3. 원본 분석과 최신 정보 사이에 불일치가 있다면 최신 정보를 우선시하고 그 이유를 설명하세요.
        4. 마크다운 형식으로 구조화된 분석 결과를 제공하세요.
        5. 결론 부분에 최신 정보를 바탕으로 한 추가 인사이트를 제공하세요.
        
        통합된 분석 결과:
        """
        
        response = self.gemini_model.generate_content(prompt)
        return response.text
    
    def generate_answer(
        self, 
        question: str, 
        context: str, 
        analysis_results: Dict[str, Any],
        use_cot: bool = True,
        expert_mode: bool = False
    ) -> str:
        """
        사용자 질문에 대한 답변을 생성합니다.
        
        Args:
            question: 사용자 질문
            context: 원본 문서 텍스트
            analysis_results: 분석 결과 딕셔너리
            use_cot: Chain of Thought 추론 사용 여부
            expert_mode: 전문가 모드 활성화 여부
            
        Returns:
            생성된 답변
        """
        # 컨텍스트 준비
        context_parts = [
            f"원본 문서 내용: {context[:2000]}...",  # 원본 문서의 일부만 사용
            f"분석 결과: {analysis_results['analysis']}",
            f"요약: {analysis_results['summary']}",
            f"권장사항: {analysis_results['recommendations']}"
        ]
        
        if "enhanced_analysis" in analysis_results:
            context_parts.append(f"최신 정보 통합 분석: {analysis_results['enhanced_analysis']}")
        
        combined_context = "\n\n".join(context_parts)
        
        # 프롬프트 구성
        system_prompt = """
        당신은 국책과제 전문가 AI입니다. 사용자의 질문에 대해 정확하고 유용한 답변을 제공해야 합니다.
        제공된 문서 내용과 분석 결과를 바탕으로 답변하되, 문서에 없는 내용은 명확히 구분하여 표시해주세요.
        답변은 논리적이고 구조화되어야 하며, 필요한 경우 마크다운 형식을 사용하여 가독성을 높여주세요.
        """
        
        if expert_mode:
            system_prompt += """
            전문가 모드가 활성화되었습니다. 보다 전문적이고 깊이 있는 분석과 통찰력을 제공해주세요.
            관련 법규, 정책 배경, 유사 사례 등을 포함하여 더 포괄적인 답변을 제공하세요.
            """
        
        if use_cot:
            prompt = f"""
            {system_prompt}
            
            다음은 국책과제 문서와 그 분석 결과입니다:
            
            {combined_context}
            
            사용자 질문: {question}
            
            단계별로 생각해보겠습니다:
            1. 질문의 핵심 의도 파악
            2. 관련 정보 식별
            3. 정보 분석 및 연결
            4. 답변 구성
            
            1. 질문의 핵심 의도:
            """
        else:
            prompt = f"""
            {system_prompt}
            
            다음은 국책과제 문서와 그 분석 결과입니다:
            
            {combined_context}
            
            사용자 질문: {question}
            
            답변:
            """
        
        response = self.gemini_model.generate_content(prompt)
        
        if use_cot:
            # CoT 결과에서 최종 답변만 추출
            full_response = response.text
            if "답변:" in full_response:
                answer_parts = full_response.split("답변:")
                return answer_parts[-1].strip()
            elif "4. 답변 구성:" in full_response:
                answer_parts = full_response.split("4. 답변 구성:")
                return answer_parts[-1].strip()
            else:
                return full_response
        else:
            return response.text
    
    def compare_projects(
        self, 
        project1: Dict[str, Any], 
        project2: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        두 국책과제를 비교 분석합니다.
        
        Args:
            project1: 첫 번째 프로젝트 정보
            project2: 두 번째 프로젝트 정보
            
        Returns:
            비교 분석 결과 딕셔너리
        """
        prompt = f"""
        당신은 국책과제 전문가 AI입니다. 다음 두 국책과제를 비교 분석해주세요.
        
        프로젝트 1: {project1['filename']}
        분석 결과:
        {project1['analysis']['analysis']}
        요약:
        {project1['analysis']['summary']}
        
        프로젝트 2: {project2['filename']}
        분석 결과:
        {project2['analysis']['analysis']}
        요약:
        {project2['analysis']['summary']}
        
        다음 세 가지 측면에서 비교 분석 결과를 제공해주세요:
        
        1. 주요 차이점: 두 프로젝트 간의 주요 차이점을 분석하세요.
        2. 유사점: 두 프로젝트 간의 유사점을 분석하세요.
        3. 종합 평가: 두 프로젝트의 강점과 약점을 비교하고, 어떤 프로젝트가 어떤 측면에서 더 우수한지 평가하세요.
        
        각 섹션은 마크다운 형식으로 구조화하여 제공해주세요.
        """
        
        response = self.gemini_model.generate_content(prompt)
        full_text = response.text
        
        # 결과 파싱
        differences = ""
        similarities = ""
        evaluation = ""
        
        if "# 주요 차이점" in full_text:
            parts = full_text.split("# 주요 차이점")
            if len(parts) > 1:
                if "# 유사점" in parts[1]:
                    differences = parts[1].split("# 유사점")[0].strip()
                else:
                    differences = parts[1].strip()
        
        if "# 유사점" in full_text:
            parts = full_text.split("# 유사점")
            if len(parts) > 1:
                if "# 종합 평가" in parts[1]:
                    similarities = parts[1].split("# 종합 평가")[0].strip()
                else:
                    similarities = parts[1].strip()
        
        if "# 종합 평가" in full_text:
            parts = full_text.split("# 종합 평가")
            if len(parts) > 1:
                evaluation = parts[1].strip()
        
        # 파싱이 제대로 되지 않은 경우 전체 텍스트 반환
        if not differences and not similarities and not evaluation:
            return {
                "differences": "# 주요 차이점\n\n" + full_text,
                "similarities": "",
                "evaluation": ""
            }
        
        return {
            "differences": "# 주요 차이점\n\n" + differences,
            "similarities": "# 유사점\n\n" + similarities,
            "evaluation": "# 종합 평가\n\n" + evaluation
        }
    
    def perform_deep_analysis(
        self,
        project_text: str,
        analysis_results: Dict[str, Any],
        focus_area: str = "전체"
    ) -> Dict[str, str]:
        """
        국책과제에 대한 심층 분석을 수행합니다.
        
        Args:
            project_text: 프로젝트 원문 텍스트
            analysis_results: 기본 분석 결과
            focus_area: 심층 분석 초점 영역 (예: "예산", "기술적 타당성", "시장성", "전체")
            
        Returns:
            심층 분석 결과 딕셔너리
        """
        # 기본 분석 결과 추출
        analysis = analysis_results.get("analysis", "")
        summary = analysis_results.get("summary", "")
        recommendations = analysis_results.get("recommendations", "")
        
        # 심층 분석 프롬프트 구성
        system_prompt = """
        당신은 국책과제 심층 분석 전문가 AI입니다. 제공된 국책과제 문서와 기본 분석 결과를 바탕으로 
        더 깊이 있는 분석을 수행해야 합니다. 분석은 객관적이고 근거에 기반해야 하며, 
        국책과제의 성공 가능성과 영향력을 평가하는 데 중점을 두어야 합니다.
        """
        
        # 초점 영역에 따른 프롬프트 조정
        if focus_area == "예산":
            analysis_prompt = """
            국책과제의 예산 측면에 초점을 맞추어 심층 분석을 수행하세요:
            1. 예산 규모의 적절성: 과제 목표와 범위에 비해 예산이 적절한지 평가
            2. 예산 배분의 효율성: 각 항목별 예산 배분이 효율적인지 분석
            3. 비용 대비 효과: 투입 예산 대비 기대 효과의 타당성 평가
            4. 유사 과제 비교: 유사한 규모와 목표를 가진 다른 국책과제와의 예산 비교
            5. 위험 요소: 예산 관련 잠재적 위험 요소 식별
            """
        elif focus_area == "기술적 타당성":
            analysis_prompt = """
            국책과제의 기술적 타당성에 초점을 맞추어 심층 분석을 수행하세요:
            1. 기술적 혁신성: 제안된 기술의 혁신성과 차별성 평가
            2. 기술 구현 가능성: 현재 기술 수준에서 구현 가능성 분석
            3. 기술적 위험 요소: 잠재적 기술적 장애물 및 해결 방안 식별
            4. 기술 로드맵: 기술 개발 로드맵의 현실성 평가
            5. 기술 경쟁력: 국내외 유사 기술과의 경쟁력 비교
            """
        elif focus_area == "시장성":
            analysis_prompt = """
            국책과제의 시장성에 초점을 맞추어 심층 분석을 수행하세요:
            1. 시장 수요: 개발 기술/서비스에 대한 시장 수요 분석
            2. 상업화 가능성: 연구 결과의 상업화 가능성 평가
            3. 경제적 파급 효과: 과제 수행으로 인한 경제적 파급 효과 예측
            4. 시장 진입 전략: 시장 진입 전략의 적절성 평가
            5. 경쟁 환경: 관련 시장의 경쟁 환경 분석
            """
        else:  # 전체
            analysis_prompt = """
            국책과제에 대한 종합적인 심층 분석을 수행하세요:
            1. 정책적 부합성: 국가 정책 방향과의 부합성 평가
            2. 기술적 타당성: 기술 개발 목표와 방법론의 타당성 분석
            3. 경제적 효율성: 투입 자원 대비 경제적 효과 분석
            4. 실행 가능성: 추진 체계와 일정의 현실성 평가
            5. 지속 가능성: 과제 종료 후 성과의 지속 가능성 분석
            6. SWOT 분석: 강점, 약점, 기회, 위협 요소 분석
            """
        
        prompt = f"""
        {system_prompt}
        
        국책과제 원문 내용(일부):
        {project_text[:3000]}...
        
        기본 분석 결과:
        {analysis}
        
        요약:
        {summary}
        
        권장사항:
        {recommendations}
        
        {analysis_prompt}
        
        각 분석 항목에 대해 구체적인 근거와 예시를 제시하고, 마크다운 형식으로 구조화된 분석 결과를 제공해주세요.
        결론 부분에는 종합적인 평가와 함께 과제의 성공을 위한 구체적인 제안을 포함해주세요.
        """
        
        # Gemini API 호출
        response = self.gemini_model.generate_content(prompt)
        full_text = response.text
        
        # 결과 구조화
        sections = {}
        
        # 섹션 추출 (마크다운 헤더 기준)
        import re
        headers = re.findall(r'##? ([^\n]+)', full_text)
        
        if headers:
            for i, header in enumerate(headers):
                start_pattern = f'##? {re.escape(header)}'
                start_match = re.search(start_pattern, full_text)
                if start_match:
                    start_pos = start_match.start()
                    
                    # 다음 헤더 찾기
                    if i < len(headers) - 1:
                        next_pattern = f'##? {re.escape(headers[i+1])}'
                        next_match = re.search(next_pattern, full_text)
                        if next_match:
                            end_pos = next_match.start()
                            sections[header] = full_text[start_pos:end_pos].strip()
                    else:
                        # 마지막 헤더
                        sections[header] = full_text[start_pos:].strip()
        
        # 섹션이 추출되지 않은 경우 전체 텍스트 반환
        if not sections:
            return {
                "full_analysis": full_text,
                "sections": {}
            }
        
        return {
            "full_analysis": full_text,
            "sections": sections
        }
    
    def generate_advanced_qa(
        self,
        question: str,
        project_text: str,
        analysis_results: Dict[str, Any],
        deep_analysis_results: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        심층 분석 결과를 활용한 고급 질의응답을 수행합니다.
        
        Args:
            question: 사용자 질문
            project_text: 프로젝트 원문 텍스트
            analysis_results: 기본 분석 결과
            deep_analysis_results: 심층 분석 결과 (있는 경우)
            
        Returns:
            질의응답 결과 딕셔너리
        """
        # 컨텍스트 준비
        context_parts = [
            f"원본 문서 내용(일부): {project_text[:2000]}...",
            f"분석 결과: {analysis_results.get('analysis', '')}",
            f"요약: {analysis_results.get('summary', '')}",
            f"권장사항: {analysis_results.get('recommendations', '')}"
        ]
        
        # 심층 분석 결과가 있으면 추가
        if deep_analysis_results and "full_analysis" in deep_analysis_results:
            context_parts.append(f"심층 분석 결과: {deep_analysis_results['full_analysis']}")
        
        combined_context = "\n\n".join(context_parts)
        
        # 프롬프트 구성
        system_prompt = """
        당신은 국책과제 전문가 AI입니다. 사용자의 질문에 대해 정확하고 심층적인 답변을 제공해야 합니다.
        제공된 문서 내용, 기본 분석 결과, 심층 분석 결과를 바탕으로 답변하되, 다음 원칙을 따르세요:
        
        1. 답변은 근거에 기반해야 합니다. 문서에서 직접 인용할 수 있는 부분은 인용하세요.
        2. 문서에 명시되지 않은 내용은 추론임을 분명히 표시하세요.
        3. 답변은 논리적이고 구조화되어야 합니다.
        4. 가능한 경우, 다양한 관점에서 질문을 분석하세요.
        5. 마크다운 형식을 사용하여 가독성을 높이세요.
        """
        
        prompt = f"""
        {system_prompt}
        
        다음은 국책과제 문서와 그 분석 결과입니다:
        
        {combined_context}
        
        사용자 질문: {question}
        
        단계별로 생각해보겠습니다:
        1. 질문의 핵심 의도 파악
        2. 관련 정보 식별 및 분석
        3. 다양한 관점 고려
        4. 근거 기반 답변 구성
        
        1. 질문의 핵심 의도:
        """
        
        # Gemini API 호출
        response = self.gemini_model.generate_content(prompt)
        full_response = response.text
        
        # 답변 추출
        answer = ""
        reasoning = ""
        
        # 추론 과정과 최종 답변 분리
        if "4. 근거 기반 답변 구성:" in full_response:
            parts = full_response.split("4. 근거 기반 답변 구성:")
            reasoning = parts[0].strip()
            answer = parts[1].strip()
        elif "답변:" in full_response:
            parts = full_response.split("답변:")
            reasoning = parts[0].strip()
            answer = parts[1].strip()
        else:
            # 구분이 명확하지 않은 경우
            reasoning = "질문 분석 과정이 명시적으로 구분되지 않았습니다."
            answer = full_response
        
        return {
            "answer": answer,
            "reasoning": reasoning,
            "full_response": full_response
        }
    
    def check_hwp_content_freshness(self, hwp_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        HWP 문서 내용 및 메타데이터의 최신성을 평가합니다.
        
        Args:
            hwp_content: HWP 파일에서 추출한 텍스트 내용
            metadata: HWP 파일에서 추출한 메타데이터
            
        Returns:
            최신성 평가 결과 및 권장 사항을 포함한 딕셔너리
        """
        logger = logging.getLogger('freshness_check')
        
        if not self.perplexity_api_key:
            return {
                "error": "Perplexity API 키가 설정되지 않아 최신성 평가를 수행할 수 없습니다."
            }
        
        start_time = time.time()
        
        # 문서 내용에서 국책과제 관련 핵심 키워드 추출
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000,
            chunk_overlap=1000
        )
        
        # 텍스트가 너무 길면 분할하여 처리
        if len(hwp_content) > 10000:
            chunks = text_splitter.split_text(hwp_content)
            sample_text = chunks[0]  # 첫 번째 청크만 사용
        else:
            sample_text = hwp_content
        
        # 메타데이터 정보 추출
        creation_date = metadata.get("생성일자", "알 수 없음")
        last_modified = metadata.get("수정일자", "알 수 없음")
        author = metadata.get("작성자", "알 수 없음")
        title = metadata.get("제목", "알 수 없음")
        
        # 핵심 용어 추출
        key_terms = self.extract_key_terms(sample_text)
        
        # Perplexity에 최신성 평가 쿼리 전송
        metadata_info = f"""
        - 제목: {title}
        - 작성자: {author}
        - 생성일자: {creation_date}
        - 수정일자: {last_modified}
        """
        
        # 메타데이터와 내용 최신성 평가 요청
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        # 국책과제 내용 요약 쿼리
        summary_prompt = f"""
        다음은 HWP 문서에서 추출한 내용과 메타데이터입니다:
        
        {metadata_info}
        
        문서 내용 일부:
        {sample_text[:3000]}...
        
        핵심 키워드: {', '.join(key_terms)}
        
        이 문서의 내용이 현재({datetime.now().strftime('%Y년 %m월 %d일')}) 기준으로 최신 정보인지 평가해주세요. 
        특히 다음 사항을 확인해주세요:
        1. 문서에 언급된 정책이나 제도가 현재도 유효한지
        2. 최신 국책과제 동향과 부합하는지
        3. 최근 변경된 정책이나 법규가 반영되었는지
        4. 해당 분야의 최신 기술 트렌드가 반영되었는지
        
        평가 결과는 다음 형식으로 제공해주세요:
        1. 최신성 평가 (1-10점)
        2. 업데이트가 필요한 정보 목록
        3. 추가되어야 할 최신 정보 요약
        4. 전반적인 평가 의견
        """
        
        data = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You are a Korean government policy expert. Analyze the freshness of document content and provide accurate evaluation."},
                {"role": "user", "content": summary_prompt}
            ],
            "max_tokens": 4000,
            "temperature": 0.2,
            "stream": False
        }
        
        try:
            logger.info("HWP 문서 최신성 평가 요청 시작")
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=data,
                timeout=40  # 타임아웃 40초로 설정
            )
            
            if response.status_code == 200:
                result = response.json()
                freshness_evaluation = result["choices"][0]["message"]["content"]
                
                # 웹에서 최신 정보 검색 (이전에 구현한 search_web 메서드 활용)
                latest_info = self.search_web(key_terms)
                
                # 최종 결과 생성
                return {
                    "freshness_evaluation": freshness_evaluation,
                    "latest_info": latest_info,
                    "metadata": {
                        "creation_date": creation_date,
                        "last_modified": last_modified,
                        "author": author,
                        "title": title
                    },
                    "key_terms": key_terms
                }
            else:
                error_msg = f"Perplexity API 오류 (상태 코드: {response.status_code}): {response.text}"
                logger.error(error_msg)
                return {
                    "error": error_msg,
                    "metadata": {
                        "creation_date": creation_date,
                        "last_modified": last_modified,
                        "author": author,
                        "title": title
                    }
                }
                
        except Exception as e:
            error_msg = f"최신성 평가 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "metadata": {
                    "creation_date": creation_date,
                    "last_modified": last_modified,
                    "author": author,
                    "title": title
                }
            }
            
    def suggest_updates(self, hwp_content: str, freshness_result: Dict[str, Any]) -> Dict[str, str]:
        """
        HWP 문서 내용을 최신 정보로 업데이트하기 위한 제안사항을 생성합니다.
        
        Args:
            hwp_content: HWP 파일에서 추출한 텍스트 내용
            freshness_result: check_hwp_content_freshness 메서드의 결과
            
        Returns:
            업데이트 제안사항이 포함된 딕셔너리
        """
        if "error" in freshness_result:
            return {
                "error": freshness_result["error"]
            }
            
        # 최신성 평가 및 최신 정보 추출
        freshness_evaluation = freshness_result.get("freshness_evaluation", "")
        latest_info = freshness_result.get("latest_info", "")
        
        # 업데이트가 필요한 영역 분석
        # 일반적인 패턴 탐지 (예: 날짜, 금액, 비율 등)
        def extract_dates(text):
            import re
            # 날짜 패턴 (YYYY.MM.DD, YYYY-MM-DD, YYYY년 MM월 DD일 등)
            date_patterns = [
                r'\d{4}[./-]\d{1,2}[./-]\d{1,2}',
                r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
                r'\d{2}[./-]\d{1,2}[./-]\d{1,2}'  # YY.MM.DD 형식
            ]
            
            dates = []
            for pattern in date_patterns:
                dates.extend(re.findall(pattern, text))
            
            return dates
        
        def extract_amounts(text):
            import re
            # 금액 패턴 (000원, 000만원, 000억원 등)
            amount_patterns = [
                r'\d{1,3}(,\d{3})*원',
                r'\d+\s*(만|억|조)\s*원',
                r'\d{1,3}(,\d{3})*\s*(달러|유로|엔)'
            ]
            
            amounts = []
            for pattern in amount_patterns:
                amounts.extend(re.findall(pattern, text))
            
            return amounts
        
        # 주요 날짜 및 금액 추출
        dates = extract_dates(hwp_content[:10000])  # 처음 10,000자만 분석
        amounts = extract_amounts(hwp_content[:10000])
        
        # Gemini 모델을 사용하여 업데이트 제안 생성
        prompt = f"""
        다음은 HWP 문서 내용의 최신성 평가 결과와 최신 정보입니다:
        
        [최신성 평가]
        {freshness_evaluation}
        
        [최신 정보]
        {latest_info}
        
        [문서에서 발견된 주요 날짜]
        {', '.join(dates[:10]) if dates else '주요 날짜를 찾을 수 없음'}
        
        [문서에서 발견된 주요 금액]
        {', '.join(amounts[:10]) if amounts else '주요 금액을 찾을 수 없음'}
        
        [핵심 키워드]
        {', '.join(key_terms)}
        
        이 정보를 바탕으로 문서 내용을 최신 정보로 업데이트하기 위한 구체적인 제안사항을 다음 항목으로 정리해주세요:
        
        1. 삭제 또는 수정이 필요한 내용: 현재 유효하지 않거나 오래된 정보를 구체적으로 명시
        2. 추가해야 할 최신 정보: 최근 정책, 지원사항, 법규 등 추가되어야 할 정보
        3. 수정이 필요한 수치 데이터: 날짜, 금액, 비율 등이 최신 정보와 다른 경우
        4. 참고해야 할 최신 자료: 참고할 수 있는 최신 보고서, 정책 문서, 웹사이트 등
        5. 종합 권장사항: 문서 업데이트를 위한 전반적인 조언
        
        각 항목은 세부 내용을 포함하여 구체적으로 작성해주세요. 특히 최근 정책 변화나 신규 지원 사항을 강조해주세요.
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            
            # 결과 파싱 및 반환
            result = {
                "update_suggestions": response.text,
                "freshness_evaluation": freshness_evaluation,
                "latest_info": latest_info
            }
            
            return result
            
        except Exception as e:
            return {
                "error": f"업데이트 제안 생성 중 오류 발생: {str(e)}",
                "freshness_evaluation": freshness_evaluation,
                "latest_info": latest_info
            }
    
    def process_and_analyze_hwp(self, hwp_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        HWP 문서 내용을 종합적으로 처리하고 분석합니다.
        모든 문서 타입(국책과제, 법률, 논문)에 대한 자동 감지 및 분석을 지원합니다.
        
        Args:
            hwp_content: HWP 파일에서 추출한 텍스트 내용
            metadata: HWP 파일에서 추출한 메타데이터
            
        Returns:
            종합 분석 결과
        """
        start_time = time.time()
        
        # 문서 타입 감지
        document_type = KoreanTextProcessor.detect_document_type(hwp_content)
        self.logger.info(f"감지된 문서 타입: {document_type}")
        
        # 여러 분석 작업을 병렬로 실행
        tasks = {
            "freshness": lambda: self.check_hwp_content_freshness(hwp_content, metadata),
            "korean_analysis": lambda: self.analyze_korean_text(hwp_content),
            "comprehensive_analysis": lambda: self.analyze_project_comprehensively(hwp_content, metadata)
        }
        
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(task): name for name, task in tasks.items()}
            
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    self.logger.error(f"{name} 분석 중 오류 발생: {str(e)}")
                    results[name] = {"error": str(e)}
        
        # 분석 결과에 기반한 업데이트 제안 생성
        if "freshness" in results and "error" not in results["freshness"]:
            results["update_suggestions"] = self.suggest_updates(hwp_content, results["freshness"])
        
        # 문서 타입별 특화 분석 추가
        if document_type == "법률":
            self.logger.info("법률 문서 특화 분석 추가 중")
            try:
                legal_prompt = f"""
                    다음 법률 문서에 대해 추가적인 법적 위험 요소 분석과 유사 판례 검토를 수행하세요.
                    
                    문서:
                    {hwp_content[:8000]}
                    
                    다음 항목에 초점을 맞추어 분석해주세요:
                    1. 법적 위험 요소 및 쟁점
                    2. 관련 판례 및 법적 선례
                    3. 법적 권고사항
                """
                legal_analysis, _ = self._call_gemini_with_metrics(legal_prompt)
                results["legal_specific_analysis"] = legal_analysis
            except Exception as e:
                self.logger.error(f"법률 특화 분석 중 오류 발생: {str(e)}")
                results["legal_specific_analysis"] = {"error": str(e)}
                
        elif document_type == "논문":
            self.logger.info("논문 특화 분석 추가 중")
            try:
                academic_prompt = f"""
                    다음 학술 논문에 대해 추가적인 연구 방법론 평가와 학술적 의의 분석을 수행하세요.
                    
                    논문:
                    {hwp_content[:8000]}
                    
                    다음 항목에 초점을 맞추어 분석해주세요:
                    1. 연구 방법론 타당성 평가
                    2. 선행 연구와의 관계 및 차별점
                    3. 학술적 공헌도 및 후속 연구 방향
                """
                academic_analysis, _ = self._call_gemini_with_metrics(academic_prompt)
                results["academic_specific_analysis"] = academic_analysis
            except Exception as e:
                self.logger.error(f"논문 특화 분석 중 오류 발생: {str(e)}")
                results["academic_specific_analysis"] = {"error": str(e)}
        
        elapsed_time = time.time() - start_time
        
        # 전체 결과 패키징
        final_result = {
            "document_type": document_type,
            "analysis_results": results,
            "metadata": metadata,
            "processing_time": {
                "total_seconds": round(elapsed_time, 2)
            },
            "performance_metrics": self.metrics.get_summary()
        }
        
        return final_result
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        성능 통계 정보를 반환합니다.
        
        Returns:
            성능 지표 딕셔너리
        """
        return self.metrics.get_summary()
    
    def analyze_korean_text(self, text: str) -> Dict[str, Any]:
        """
        한국어 텍스트 분석을 수행합니다.
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            한국어 텍스트 분석 결과
        """
        # 텍스트 정제
        cleaned_text = KoreanTextProcessor.clean_text(text)
        
        # 구조 분석
        structure = KoreanTextProcessor.analyze_text_structure(cleaned_text)
        
        # 용어 추출
        terms = KoreanTextProcessor.extract_korean_terms(cleaned_text)
        noun_phrases = KoreanTextProcessor.extract_noun_phrases(cleaned_text)
        
        # 도메인 용어 매핑
        domain_mapping = KoreanTextProcessor.map_to_domain_terms(terms + noun_phrases)
        
        return {
            "structure": structure,
            "terms": terms[:50],  # 상위 50개만 반환
            "noun_phrases": noun_phrases[:30],  # 상위 30개만 반환
            "domain_mapping": domain_mapping
        }
    
    def enhance_analysis_with_korean_nlp(self, original_analysis: str, text_analysis: Dict[str, Any]) -> str:
        """
        한국어 NLP 분석 결과를 활용하여 분석을 향상시킵니다.
        
        Args:
            original_analysis: 원본 분석 결과
            text_analysis: 한국어 텍스트 분석 결과
            
        Returns:
            향상된 분석 결과
        """
        # 분석 결과에서 유용한 정보 추출
        structure = text_analysis.get("structure", {})
        domain_mapping = text_analysis.get("domain_mapping", {})
        
        # 도메인 용어 분류 정보 생성
        domain_info = ""
        for category, terms in domain_mapping.items():
            if terms:
                domain_info += f"- {category}: {', '.join(terms[:5])}\n"
        
        # 문서 구조 정보 생성
        structure_info = f"""
- 문서 길이: {structure.get('length', 0)}자
- 문단 수: {structure.get('paragraph_count', 0)}
- 섹션 수: {structure.get('section_count', 0)}
- 표/그림 참조: {structure.get('figure_ref_count', 0)}개
        """
        
        prompt = f"""
        당신은 국책과제 전문가 AI입니다. 다음 정보를 통합하여 더 정확하고 상세한 분석 결과를 생성해주세요.
        
        1. 원본 분석 결과:
        {original_analysis}
        
        2. 한국어 텍스트 구조 분석:
        {structure_info}
        
        3. 국책과제 관련 도메인 용어 분류:
        {domain_info}
        
        다음 지침에 따라 통합된 분석 결과를 생성해주세요:
        1. 원본 분석의 주요 내용을 유지하되, 문서 구조와 도메인 용어 분석을 통해 얻은 인사이트를 통합하세요.
        2. 문서의 구조적 특성을 고려하여 더 정확한 맥락 파악을 제공하세요.
        3. 도메인 용어 분류를 활용하여 국책과제의 핵심 영역과 초점을 더 명확히 분석하세요.
        4. 마크다운 형식으로 구조화된 분석 결과를 제공하세요.
        5. 본문에서 발견된 중요 섹션과 도메인 용어를 강조하여 보여주세요.
        
        통합된 분석 결과:
        """
        
        try:
            enhanced_content, _ = self._call_gemini_with_metrics(prompt)
            return enhanced_content
        except Exception as e:
            self.logger.error(f"한국어 NLP 기반 분석 향상 중 오류 발생: {str(e)}")
            return original_analysis
    
    def analyze_project_comprehensively(
        self,
        project_text: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        국책과제, 법률, 논문 등 다양한 문서 타입에 대한 종합적인 분석을 제공합니다.
        
        Args:
            project_text: 프로젝트 원문 텍스트
            metadata: 메타데이터 (선택사항)
            
        Returns:
            종합 분석 결과
        """
        start_time = time.time()
        
        # 1. 한국어 텍스트 분석
        self.logger.info("한국어 텍스트 분석 시작")
        korean_analysis = self.analyze_korean_text(project_text)
        
        # 2. 문서 타입 감지
        self.logger.info("문서 타입 감지 중")
        document_type = KoreanTextProcessor.detect_document_type(project_text)
        self.logger.info(f"감지된 문서 타입: {document_type}")
        
        # 3. 키워드 추출
        self.logger.info("핵심 키워드 추출 중")
        key_terms = self.extract_key_terms(project_text)
        
        # 4. 문서 타입에 따른 분석 프롬프트 구성
        analysis_prompts = {
            "국책과제": f"""
                다음은 한국 국책과제 관련 문서입니다. 이 문서를 분석하여 주요 내용, 목적, 대상, 지원 범위, 
                예산, 기간, 평가 기준 등의 핵심 정보를 요약해주세요.
                
                문서:
                {project_text[:15000]}
                
                다음 형식으로 분석 결과를 제공해주세요:
                
                # 국책과제 분석 요약
                
                ## 1. 개요
                [과제의 목적과 배경을 간략히 설명]
                
                ## 2. 주요 내용
                [과제의 핵심 내용 요약]
                
                ## 3. 지원 대상 및 범위
                [지원 대상, 자격 요건, 지원 범위 등]
                
                ## 4. 예산 및 기간
                [예산 규모, 사업 기간, 단계별 지원 등]
                
                ## 5. 평가 기준
                [선정 및 평가 기준, 우대 사항 등]
                
                ## 6. 주요 특징
                [이 과제의 독특한 특징이나 중요 포인트]
                
                ## 7. 분석 및 제언
                [과제의 의의, 시사점, 신청 시 고려사항 등]
            """,
            
            "법률": f"""
                다음은 법률 관련 문서입니다. 이 문서를 분석하여 주요 내용, 법적 의미, 조항, 권리와 의무, 
                법적 효과 등의 핵심 정보를 요약해주세요.
                
                문서:
                {project_text[:15000]}
                
                다음 형식으로 분석 결과를 제공해주세요:
                
                # 법률 문서 분석 요약
                
                ## 1. 개요
                [문서의 종류와 목적을 간략히 설명]
                
                ## 2. 주요 조항
                [핵심 조항 및 내용 요약]
                
                ## 3. 법적 권리와 의무
                [각 당사자의 권리와 의무 관계]
                
                ## 4. 법적 효과
                [해당 문서가 가지는 법적 효과 및 영향]
                
                ## 5. 위험 요소
                [잠재적 법적 위험이나 논쟁 가능성]
                
                ## 6. 관련 법령
                [관련된 법률, 판례 등 참고 사항]
                
                ## 7. 법적 조언 및 제언
                [주의해야 할 법적 사항 및 권장 조치]
            """,
            
            "논문": f"""
                다음은 학술 논문 관련 문서입니다. 이 문서를 분석하여 연구 목적, 방법론, 주요 발견, 
                결론, 한계점 등의 핵심 정보를 요약해주세요.
                
                문서:
                {project_text[:15000]}
                
                다음 형식으로 분석 결과를 제공해주세요:
                
                # 논문 분석 요약
                
                ## 1. 연구 개요
                [연구 주제와 목적을 간략히 설명]
                
                ## 2. 연구 방법
                [사용된 연구 방법론, 실험 설계, 데이터 수집 방법 등]
                
                ## 3. 주요 결과
                [연구의 핵심 발견 및 결과]
                
                ## 4. 분석 및 논의
                [결과에 대한 저자의 분석과 논의 사항]
                
                ## 5. 결론 및 시사점
                [연구의 최종 결론과 시사점]
                
                ## 6. 한계 및 향후 연구
                [연구의 한계와 향후 연구 제안]
                
                ## 7. 학술적 가치
                [해당 연구의 학술적 기여도와 중요성]
            """
        }
        
        # 기본값으로 국책과제 프롬프트 사용
        prompt = analysis_prompts.get(document_type, analysis_prompts["국책과제"])
        
        try:
            # 5. 기본 분석 실행
            self.logger.info(f"{document_type} 분석 수행 중")
            basic_analysis, basic_analysis_time = self._call_gemini_with_metrics(prompt)
            self.logger.info(f"기본 분석 완료 (소요 시간: {basic_analysis_time:.2f}초)")
            
            # 6. 한국어 NLP로 향상된 분석
            self.logger.info("한국어 NLP로 분석 강화 중")
            enhanced_analysis = self.enhance_analysis_with_korean_nlp(
                basic_analysis, 
                korean_analysis
            )
            
            # 7. 웹 검색으로 최신 정보 보강 (선택적)
            latest_info = None
            if len(key_terms) >= 3:
                self.logger.info("웹 검색으로 최신 정보 수집 중")
                try:
                    latest_info = self.search_web(key_terms)
                    
                    # 최신 정보로 분석 보강
                    if latest_info:
                        self.logger.info("최신 정보로 분석 결과 보강 중")
                        enhanced_analysis = self.enhance_analysis(enhanced_analysis, latest_info)
                except Exception as e:
                    self.logger.warning(f"웹 검색 중 오류 발생: {str(e)}")
            
            total_time = time.time() - start_time
            
            # 8. 종합 결과 반환
            result = {
                "document_type": document_type,
                "enhanced_analysis": enhanced_analysis,
                "basic_analysis": basic_analysis,
                "korean_text_analysis": korean_analysis,
                "key_terms": key_terms,
                "latest_info": latest_info,
                "metadata": metadata,
                "processing_time": {
                    "total_seconds": round(total_time, 2),
                    "basic_analysis_seconds": round(basic_analysis_time, 2)
                },
                "performance_metrics": self.metrics.get_summary()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"종합 분석 중 오류 발생: {str(e)}")
            return {
                "error": f"분석 중 오류가 발생했습니다: {str(e)}",
                "document_type": document_type,
                "key_terms": key_terms,
                "korean_text_analysis": korean_analysis,
                "processing_time": {
                    "total_seconds": round(time.time() - start_time, 2)
                }
            } 