import streamlit as st
import os
from dotenv import load_dotenv
from analyzer import ProjectAnalyzer
from hwp_utils import HwpHandler
from hybrid_search import HybridSearchEngine
from hwp_to_latex import HwpToLatexConverter
import tempfile
import pandas as pd
import time
import json
from pathlib import Path
import logging
import requests
import shutil
import gc

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger('streamlit_app')

# Streamlit 캐싱 함수
@st.cache_data(ttl=3600, show_spinner=False)
def cached_analyze_project(analyzer, text, method="hybrid"):
    """ProjectAnalyzer.analyze_project 메서드의 캐싱 래퍼"""
    return analyzer.analyze_project(text, method)

@st.cache_data(ttl=3600, show_spinner=False)
def cached_extract_key_insights(analyzer, text, num_insights=5):
    """ProjectAnalyzer.extract_key_insights 메서드의 캐싱 래퍼"""
    return analyzer.extract_key_insights(text, num_insights)

@st.cache_data(ttl=3600, show_spinner=False)
def cached_analyze_project_with_verification(analyzer, text, method="hybrid", verification_rounds=1):
    """ProjectAnalyzer.analyze_project_with_verification 메서드의 캐싱 래퍼"""
    return analyzer.analyze_project_with_verification(text, method, verification_rounds)

@st.cache_data(ttl=3600, show_spinner=False)
def cached_check_hwp_content_freshness(engine, hwp_content, metadata):
    """HybridSearchEngine.check_hwp_content_freshness 메서드의 캐싱 래퍼"""
    return engine.check_hwp_content_freshness(hwp_content, metadata)

@st.cache_data(ttl=3600, show_spinner=False)
def cached_suggest_updates(engine, hwp_content, freshness_result):
    """HybridSearchEngine.suggest_updates 메서드의 캐싱 래퍼"""
    return engine.suggest_updates(hwp_content, freshness_result)

# Load environment variables
load_dotenv()

# API 키 로딩 - 로컬(.env)과 Streamlit Cloud(st.secrets) 모두 지원
def get_api_key(key_name, default_value=None):
    """로컬 환경변수 또는 Streamlit secrets에서 API 키를 가져옵니다."""
    # Streamlit Cloud에서 실행 시 st.secrets에서 로드
    if key_name in st.secrets:
        return st.secrets[key_name]
    # 로컬 환경에서 실행 시 환경변수에서 로드
    return os.environ.get(key_name, default_value)

# API 키 설정
GOOGLE_API_KEY = get_api_key("GOOGLE_API_KEY")
PERPLEXITY_API_KEY = get_api_key("PERPLEXITY_API_KEY")

# Set page configuration
st.set_page_config(
    page_title="HWP & HWPX 파일 분석기",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        font-weight: 700;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        font-weight: 500;
    }
    .info-box {
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .warning-box {
        background-color: #FFF8E1;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #E8F5E9;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 4rem;
        white-space: pre-wrap;
        background-color: #F5F5F5;
        border-radius: 0.5rem 0.5rem 0 0;
        padding: 0.5rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E3F2FD;
    }
    .result-container {
        background-color: #FAFAFA;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #EEEEEE;
        margin-top: 1rem;
    }
    .upload-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 2rem;
        border: 2px dashed #BDBDBD;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
        background-color: #F5F5F5;
    }
    .error-message {
        color: #D32F2F;
        padding: 1rem;
        background-color: #FFEBEE;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .success-message {
        color: #2E7D32;
        padding: 1rem;
        background-color: #E8F5E9;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .sidebar-heading {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    
    /* 기본 라이트 모드 설정 */
    p, li, h1, h2, h3, h4, h5, h6, span {
        color: #212121 !important;
    }
    .stMarkdown {
        color: #212121 !important;
    }
    .stTextInput > div > div > input {
        color: #212121 !important;
    }
    .stSelectbox > div > div > div > div {
        color: #212121 !important;
    }
    .stMarkdown a {
        color: #1976D2 !important;
    }
    
    /* 데이터프레임과 테이블 스타일링 - 라이트 모드 */
    .dataframe {
        color: #212121 !important;
    }
    .dataframe th {
        background-color: #E3F2FD !important;
        color: #212121 !important;
    }
    .dataframe td {
        color: #212121 !important;
    }
    
    /* 코드 블록 스타일링 - 라이트 모드 */
    .stCodeBlock {
        color: #212121 !important;
    }
    
    /* 버튼 텍스트 - 라이트 모드 */
    .stButton button {
        color: #212121 !important;
        font-weight: 500 !important;
    }
    
    /* 탭 내용 텍스트 - 라이트 모드 */
    .stTabs [data-baseweb="tab-panel"] {
        color: #212121 !important;
    }
    
    /* 다크모드 지원 (고대비) */
    @media (prefers-color-scheme: dark) {
        .main-header {
            color: #FFFFFF;
        }
        .sub-header {
            color: #FFFFFF;
        }
        p, li, h1, h2, h3, h4, h5, h6, span {
            color: #FFFFFF !important;
        }
        .stMarkdown {
            color: #FFFFFF !important;
        }
        .stTextInput > div > div > input {
            color: #FFFFFF !important;
        }
        .stSelectbox > div > div > div > div {
            color: #FFFFFF !important;
        }
        .stMarkdown a {
            color: #4DABF7 !important;
        }
        .info-box, .warning-box, .success-box {
            color: #FFFFFF !important;
        }
        .stAlert {
            color: #FFFFFF !important;
        }
        
        /* 다크모드에서 정보 박스 배경색 조정 */
        div[style*="background-color: #E8F5E9"] {
            background-color: #1E3D2F !important;
        }
        div[style*="background-color: #E3F2FD"] {
            background-color: #1A2F4A !important;
        }
        div[style*="background-color: #FFF8E1"] {
            background-color: #3D3223 !important;
        }
        
        /* 다크모드에서 표 테두리 및 텍스트 가시성 향상 */
        .stDataFrame {
            border: 1px solid #3D3D3D !important;
        }
        .stDataFrame td, .stDataFrame th {
            color: #FFFFFF !important;
            border-color: #3D3D3D !important;
        }
        .stDataFrame [data-testid="stVerticalBlock"] div:has(table) {
            color: #FFFFFF !important;
        }
        
        /* 데이터프레임과 테이블 스타일링 - 다크 모드 */
        .dataframe {
            color: #FFFFFF !important;
        }
        .dataframe th {
            background-color: #1E3A5F !important;
            color: #FFFFFF !important;
        }
        .dataframe td {
            color: #FFFFFF !important;
        }
        
        /* 코드 블록 스타일링 - 다크 모드 */
        .stCodeBlock {
            color: #FFFFFF !important;
        }
        
        /* 버튼 텍스트 - 다크 모드 */
        .stButton button {
            color: #FFFFFF !important;
            font-weight: 500 !important;
        }
        
        /* 탭 내용 텍스트 - 다크 모드 */
        .stTabs [data-baseweb="tab-panel"] {
            color: #FFFFFF !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# App title and description
st.markdown('<p class="main-header">HWP & HWPX 파일 분석기</p>', unsafe_allow_html=True)
st.markdown("""
<div class="info-box">
    <p>HWP 및 HWPX 파일을 업로드하여 문서 구조, 내용, 메타데이터를 빠르게 분석하고 이해할 수 있습니다.</p>
    <p>Gemini API와 Perplexity API를 하이브리드로 활용하여 문서 분석 및 변환 기능을 제공합니다.</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "api_key" not in st.session_state:
    st.session_state.api_key = GOOGLE_API_KEY
if "perplexity_api_key" not in st.session_state:
    st.session_state.perplexity_api_key = PERPLEXITY_API_KEY
if "files_data" not in st.session_state:
    st.session_state.files_data = []
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "current_file_index" not in st.session_state:
    st.session_state.current_file_index = 0
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "perplexity_connected" not in st.session_state:
    st.session_state.perplexity_connected = False
if "perplexity_error" not in st.session_state:
    st.session_state.perplexity_error = None
if "use_hybrid_search" not in st.session_state:
    st.session_state.use_hybrid_search = False
if "expert_mode" not in st.session_state:
    st.session_state.expert_mode = False
if "analysis_option" not in st.session_state:
    st.session_state.analysis_option = "basic"
if "verification_rounds" not in st.session_state:
    st.session_state.verification_rounds = 1

def initialize_session_state():
    """세션 상태 초기화 함수"""
    # API 키 관련 세션은 이미 상단에서 초기화됨
    
    # 분석 옵션 초기화
    if "use_hybrid_search" not in st.session_state:
        st.session_state.use_hybrid_search = False
    if "expert_mode" not in st.session_state:
        st.session_state.expert_mode = False
    if "analysis_option" not in st.session_state:
        st.session_state.analysis_option = "basic"
    if "verification_rounds" not in st.session_state:
        st.session_state.verification_rounds = 1
    
    # Perplexity API 연결 상태
    if "perplexity_connected" not in st.session_state:
        st.session_state.perplexity_connected = False
    if "perplexity_error" not in st.session_state:
        st.session_state.perplexity_error = None
    
    # 파일 및 분석 데이터
    if "files_data" not in st.session_state:
        st.session_state.files_data = []
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}
    if "current_file_index" not in st.session_state:
        st.session_state.current_file_index = 0
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

# Perplexity API 연결 테스트 함수
def test_perplexity_connection(api_key):
    """Perplexity API 연결 테스트"""
    if not api_key:
        return False, "API 키가 설정되지 않았습니다. API 키를 입력해주세요."
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sonar",  # 웹 검색 기능이 있는 모델로 설정
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working?"}
            ],
            "max_tokens": 100,
            "temperature": 0.2
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=10  # 10초 타임아웃 설정
        )
        
        if response.status_code == 200:
            return True, None
        else:
            error_message = f"Perplexity API 오류 (상태 코드: {response.status_code}): {response.text}"
            logging.error(f"Perplexity API 연결 실패: {response.text}")
            return False, error_message
    
    except Exception as e:
        error_message = f"Perplexity API 연결 중 오류 발생: {str(e)}"
        logging.error(f"Perplexity API 연결 중 예외 발생: {str(e)}")
        return False, error_message

# Main app logic
def main():
    # Sidebar configuration
    with st.sidebar:
        st.title("HWP & HWPX 파일 분석기")
        
        st.markdown('<div class="sidebar-heading">API 키 설정</div>', unsafe_allow_html=True)
        
        st.session_state.api_key = st.text_input(
            "Google Gemini API 키", 
            value=st.session_state.api_key,
            type="password"
        )
        
        with st.expander("Perplexity API 설정 (선택사항)"):
            st.session_state.perplexity_api_key = st.text_input(
                "Perplexity API 키", 
                value=st.session_state.perplexity_api_key,
                type="password"
            )
        
        # 실행 환경 정보 (Streamlit Cloud/로컬)
        env_info = "Streamlit Cloud" if "STREAMLIT_SHARING_MODE" in os.environ else "로컬 환경"
        st.markdown(f"**실행 환경**: {env_info}")
        
        # 배포 환경 최적화를 위한 설정
        st.markdown('<div class="sidebar-heading">성능 설정</div>', unsafe_allow_html=True)
        
        # 메모리 사용량 설정
        memory_optimization = st.checkbox("메모리 최적화 모드", value=True, 
                                          help="대용량 파일 처리 시 메모리 사용량을 줄입니다.")
        
        # 캐시 사용 설정
        use_cache = st.checkbox("캐시 사용", value=True,
                                help="API 호출 결과를 캐시하여 성능을 향상시킵니다.")
        
        # 가비지 컬렉션 실행 버튼
        if st.button("메모리 정리"):
            # 임시 파일 정리
            try:
                temp_dir = tempfile.gettempdir()
                if os.path.exists(temp_dir):
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        if item.startswith('tmp') and os.path.isdir(item_path):
                            try:
                                shutil.rmtree(item_path)
                            except:
                                pass
                
                # 가비지 컬렉션 강제 실행
                gc.collect()
                st.success("메모리 정리 완료")
            except Exception as e:
                st.error(f"메모리 정리 중 오류 발생: {str(e)}")
        
        # Streamlit Cloud 제한을 위한 경고
        if env_info == "Streamlit Cloud":
            st.markdown("""
            <div class="warning-box">
            ⚠️ <b>Streamlit Cloud 제한 사항</b><br>
            - 파일 크기: 최대 200MB<br>
            - 처리 시간: 최대 10분<br>
            - 메모리: 약 1GB<br>
            대용량 파일은 로컬 환경에서 실행하는 것이 좋습니다.
            </div>
            """, unsafe_allow_html=True)
            
        # Streamlit 캐시 관리
        with st.expander("캐시 관리"):
            if st.button("캐시 비우기"):
                # Streamlit 캐시 초기화
                st.cache_data.clear()
                st.success("캐시를 비웠습니다.")
    
    # 세션 초기화 및 기본값 설정
    initialize_session_state()
    
    # 분석기 초기화
    if st.session_state.api_key:
        # 분석기 초기화
        analyzer = ProjectAnalyzer(st.session_state.api_key)
        
        # 하이브리드 검색 엔진 초기화 (선택적)
        hybrid_search = None
        if st.session_state.perplexity_api_key:
            hybrid_search = HybridSearchEngine(
                st.session_state.api_key, 
                st.session_state.perplexity_api_key
            )
    else:
        st.warning("Gemini API 키를 설정해주세요.")
        analyzer = None
        hybrid_search = None
    
    # Main content area
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "파일 분석", 
        "데이터 추출", 
        "문서 변환",
        "문서 비교",
        "질의응답",
        "최신성 검사"
    ])
    
    with tab1:
        st.markdown('<div class="main-header">HWP 및 HWPX 파일 분석</div>', unsafe_allow_html=True)
        
        # Gemini API 키가 설정되었는지 확인
        if not st.session_state.api_key:
            st.error("Gemini API 키를 먼저 설정해주세요.")
            return
        
        # 파일 업로드 섹션
        st.markdown('<div class="sub-header">파일 업로드</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        HWP 및 HWPX 파일을 업로드하여 내용, 메타데이터, 표, 이미지 등을 분석할 수 있습니다.
        </div>
        """, unsafe_allow_html=True)
        
        # Streamlit Cloud에서는 파일 크기 제한을 더 엄격하게 적용
        MAX_FILE_SIZE_MB = 50 if "STREAMLIT_SHARING_MODE" in os.environ else 200
        
        # 파일 크기 제한 표시
        st.markdown(f"""
        <div class="warning-box">
        ⚠️ <b>파일 크기 제한</b>: 파일당 최대 {MAX_FILE_SIZE_MB}MB까지 허용됩니다.
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_files = st.file_uploader(
            "HWP 또는 HWPX 파일 업로드",
            type=["hwp", "hwpx"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            # Process new files
            new_files = [f for f in uploaded_files if f.name not in [data["filename"] for data in st.session_state.files_data]]
            
            if new_files:
                # 파일 크기 검사
                oversized_files = []
                valid_files = []
                
                for file in new_files:
                    # 스트림의 현재 위치를 저장하고 파일 크기 확인
                    current_position = file.tell()
                    file.seek(0, os.SEEK_END)
                    file_size_mb = file.tell() / (1024 * 1024)
                    file.seek(current_position)  # 위치 복원
                    
                    if file_size_mb > MAX_FILE_SIZE_MB:
                        oversized_files.append((file.name, file_size_mb))
                    else:
                        valid_files.append(file)
                
                # 크기 초과 파일 경고
                if oversized_files:
                    st.error(f"{len(oversized_files)}개의 파일이 크기 제한({MAX_FILE_SIZE_MB}MB)을 초과했습니다.")
                    for name, size in oversized_files:
                        st.warning(f"- {name}: {size:.2f}MB")
                
                # 유효한 파일 처리
                if valid_files:
                    with st.spinner("파일을 처리 중입니다..."):
                        progress_bar = st.progress(0)
                        total_files = len(valid_files)
                        
                        for i, uploaded_file in enumerate(valid_files):
                            try:
                                # 메모리 최적화 모드 설정 적용
                                if 'memory_optimization' in locals() and memory_optimization:
                                    # 메모리 최적화 모드: 작은 청크로 처리
                                    temp_dir = tempfile.mkdtemp()
                                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                                    
                                    with open(temp_path, 'wb') as f:
                                        f.write(uploaded_file.getbuffer())
                                    
                                    # 청크 단위로 처리
                                    metadata = HwpHandler.extract_metadata(uploaded_file)
                                    
                                    # 파일 다시 열기
                                    uploaded_file.seek(0)
                                    text = HwpHandler.extract_text(uploaded_file)
                                    
                                    # 임시 파일 정리
                                    os.remove(temp_path)
                                    os.rmdir(temp_dir)
                                else:
                                    # 일반 모드: 한 번에 처리
                                    metadata = HwpHandler.extract_metadata(uploaded_file)
                                    uploaded_file.seek(0)
                                    text = HwpHandler.extract_text(uploaded_file)
                                
                                if text and metadata:
                                    # Add to session state
                                    st.session_state.files_data.append({
                                        "filename": uploaded_file.name,
                                        "metadata": metadata,
                                        "text": text,
                                        "processed": False
                                    })
                                
                                # 진행 상황 업데이트
                                progress = (i + 1) / total_files
                                progress_bar.progress(progress)
                                
                            except Exception as e:
                                st.error(f"'{uploaded_file.name}' 처리 중 오류 발생: {str(e)}")
                        
                    st.success(f"{len(valid_files)}개의 새 파일이 추가되었습니다.")
            
            # 파일 목록 표시
            file_df = pd.DataFrame([
                {
                    "파일명": data["filename"],
                    "크기 (KB)": f"{data['metadata']['file_size'] / 1024:.2f}",
                    "페이지 수": data["metadata"]["page_count"],
                    "분석 상태": "완료" if data["filename"] in st.session_state.analysis_results else "대기 중"
                } for data in st.session_state.files_data
            ])
            
            # 지원 문서 유형 및 검증 라운드 정보 안내 (강조 박스)
            st.markdown("""
            <div style="background-color: #E8F5E9; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <h4 style="margin-top: 0;">📋 분석 정보</h4>
                <p><strong>지원 문서 유형:</strong> 국책과제 보고서, 법률 문서, 학술 논문</p>
                <p><strong>처리 시간 안내:</strong> 검증 라운드가 높을수록 분석 품질은 향상되지만, 처리 시간이 크게 증가합니다.</p>
                <ul>
                    <li>자동 문서 유형 감지 기능이 활성화되어 있습니다.</li>
                    <li>문서 유형에 따라 최적화된 분석이 수행됩니다.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.dataframe(file_df, use_container_width=True)
            
            # Select file to analyze
            file_names = [data["filename"] for data in st.session_state.files_data]
            selected_file = st.selectbox(
                "분석할 파일 선택", 
                file_names,
                index=min(st.session_state.current_file_index, len(file_names)-1)
            )
            
            st.session_state.current_file_index = file_names.index(selected_file)
            current_file = st.session_state.files_data[st.session_state.current_file_index]
            
            # Display file metadata
            st.subheader("파일 정보")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**파일명:** {current_file['metadata']['filename']}")
                st.write(f"**파일 크기:** {current_file['metadata']['file_size'] / 1024:.2f} KB")
            with col2:
                st.write(f"**페이지 수:** {current_file['metadata']['page_count']}")
                if current_file['metadata']['properties'].get('title'):
                    st.write(f"**문서 제목:** {current_file['metadata']['properties']['title']}")
            
            # Display extracted text in an expander
            with st.expander("추출된 텍스트", expanded=False):
                st.text_area("원본 텍스트", current_file["text"], height=300)
            
            # Analyze button
            if st.button("선택한 파일 분석하기"):
                # 검증 라운드에 따른 안내 메시지
                verification_time_info = ""
                if st.session_state.verification_rounds == 0:
                    verification_time_info = "기본 분석 모드입니다. 예상 소요 시간: 약 30초~1분"
                elif st.session_state.verification_rounds == 1:
                    verification_time_info = "1회 검증 분석 모드입니다. 예상 소요 시간: 약 1~2분"
                elif st.session_state.verification_rounds == 2:
                    verification_time_info = "2회 검증 분석 모드입니다. 예상 소요 시간: 약 2~4분"
                else:
                    verification_time_info = "3회 검증 분석 모드입니다. 예상 소요 시간: 약 4~6분"
                
                with st.spinner(f"Gemini로 분석 중... {verification_time_info}"):
                    try:
                        # Check if analysis already exists
                        if current_file["filename"] not in st.session_state.analysis_results:
                            # 검증 라운드 설정에 따라 분석 방법 선택
                            if st.session_state.verification_rounds > 0:
                                # 검증 및 개선 과정을 포함한 분석
                                results = cached_analyze_project_with_verification(
                                    analyzer,
                                    current_file["text"],
                                    method=st.session_state.analysis_option,
                                    verification_rounds=st.session_state.verification_rounds
                                )
                            else:
                                # 기본 분석
                                results = cached_analyze_project(
                                    analyzer,
                                    current_file["text"],
                                    method=st.session_state.analysis_option
                                )
                            
                            # Add web search if hybrid search is enabled
                            if st.session_state.use_hybrid_search and not results.get("error"):
                                # Perplexity API 연결 상태 확인
                                if not st.session_state.perplexity_connected:
                                    st.warning("Perplexity API가 연결되지 않았습니다. 웹 검색 기능을 사용할 수 없습니다.")
                                    st.info("사이드바에서 Perplexity API 키를 설정하고 연결 테스트를 진행해주세요.")
                                else:
                                    with st.spinner("최신 정보 검색 중..."):
                                        # Extract key terms for search
                                        key_terms = cached_extract_key_insights(
                                            hybrid_search,
                                            results["summary"],
                                            num_insights=5
                                        )
                                        
                                        # Perform web search
                                        web_results = hybrid_search.search_web(key_terms)
                                        
                                        # Enhance analysis with web results
                                        enhanced_analysis = hybrid_search.enhance_analysis(
                                            original_analysis=results["analysis"],
                                            web_results=web_results
                                        )
                                        
                                        results["enhanced_analysis"] = enhanced_analysis
                                        results["web_results"] = web_results
                            
                            # Store results
                            st.session_state.analysis_results[current_file["filename"]] = results
                            
                            # Mark as processed
                            for i, data in enumerate(st.session_state.files_data):
                                if data["filename"] == current_file["filename"]:
                                    st.session_state.files_data[i]["processed"] = True
                                    break
                        
                        st.success("분석이 완료되었습니다!")
                        
                    except Exception as e:
                        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
            
            # Display analysis results if available
            if current_file["filename"] in st.session_state.analysis_results:
                results = st.session_state.analysis_results[current_file["filename"]]
                
                if "error" in results and results["error"]:
                    st.error(f"분석 중 오류가 발생했습니다: {results['error']}")
                else:
                    # Create tabs for different analysis results
                    analysis_tabs = st.tabs(["상세 분석", "요약", "권장사항", "검증 결과", "최신 정보 통합 분석"])
                    
                    with analysis_tabs[0]:
                        st.subheader("상세 분석")
                        st.markdown(results["analysis"])
                    
                    with analysis_tabs[1]:
                        st.subheader("요약")
                        st.markdown(results["summary"])
                    
                    with analysis_tabs[2]:
                        st.subheader("권장사항")
                        st.markdown(results["recommendations"])
                    
                    with analysis_tabs[3]:
                        st.subheader("검증 결과")
                        # 검증 결과가 있는 경우에만 표시
                        if 'verification_history' in results and results['verification_history']:
                            # 가장 최근 검증 결과
                            latest_verification = results['verification_history'][-1]
                            
                            # 검증 점수 표시
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("정확성 점수", f"{latest_verification.get('accuracy_score', 'N/A')}/10")
                            with col2:
                                st.metric("완전성 점수", f"{latest_verification.get('completeness_score', 'N/A')}/10")
                            with col3:
                                st.metric("논리적 일관성 점수", f"{latest_verification.get('consistency_score', 'N/A')}/10")
                            
                            # 발견된 문제점 및 개선 제안
                            st.subheader("발견된 문제점")
                            st.markdown(latest_verification.get('issues', '문제점이 발견되지 않았습니다.'))
                            
                            st.subheader("개선 제안")
                            st.markdown(latest_verification.get('suggestions', '개선 제안이 없습니다.'))
                            
                            # 검증 히스토리 표시 (접을 수 있는 섹션)
                            if len(results['verification_history']) > 1:
                                with st.expander("검증 히스토리 보기"):
                                    for i, verification in enumerate(results['verification_history'][:-1]):
                                        st.markdown(f"### 라운드 {i+1}")
                                        
                                        # 점수 표시
                                        st.markdown(f"""
                                        - 정확성: {verification.get('accuracy_score', 'N/A')}/10
                                        - 완전성: {verification.get('completeness_score', 'N/A')}/10
                                        - 논리적 일관성: {verification.get('consistency_score', 'N/A')}/10
                                        """)
                                        
                                        # 발견된 문제점 및 개선 제안
                                        st.markdown("**발견된 문제점:**")
                                        st.markdown(verification.get('issues', '문제점이 발견되지 않았습니다.'))
                                        
                                        st.markdown("**개선 제안:**")
                                        st.markdown(verification.get('suggestions', '개선 제안이 없습니다.'))
                                        
                                        st.markdown("---")
                        else:
                            st.info("이 분석에는 검증 결과가 없습니다. 검증 라운드를 1 이상으로 설정하고 다시 분석해보세요.")
                    
                    with analysis_tabs[4]:
                        st.subheader("최신 정보 통합 분석")
                        if "enhanced_analysis" in results:
                            st.markdown(results["enhanced_analysis"])
                            
                            with st.expander("검색된 웹 정보", expanded=False):
                                st.markdown(results["web_results"])
                        else:
                            st.info("하이브리드 검색이 활성화되지 않았거나 검색 결과가 없습니다.")
    
    with tab2:
        st.markdown('<p class="sub-header">데이터 추출</p>', unsafe_allow_html=True)
        
        if not st.session_state.files_data:
            st.warning("먼저 파일을 업로드하고 분석해주세요.")
        else:
            # Select analyzed file
            analyzed_files = [
                data["filename"] for data in st.session_state.files_data 
                if data["filename"] in st.session_state.analysis_results
            ]
            
            if not analyzed_files:
                st.warning("먼저 파일을 분석해주세요.")
            else:
                selected_file = st.selectbox(
                    "데이터 추출할 파일 선택", 
                    analyzed_files,
                    key="data_extraction_file_select"
                )
                
                # Get file data
                file_data = next(data for data in st.session_state.files_data if data["filename"] == selected_file)
                results = st.session_state.analysis_results[selected_file]
                
                # Display extracted data
                st.subheader("추출된 데이터")
                st.json(file_data["metadata"])
                
                # Display extracted text
                st.subheader("추출된 텍스트")
                st.text_area("추출된 텍스트", file_data["text"], height=300)
    
    with tab3:
        st.markdown('<p class="sub-header">문서 변환</p>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-box">
            <p>HWP 파일을 LaTeX 형식으로 변환하여 학술 논문이나 보고서 작성에 활용할 수 있습니다.</p>
            <p>Chain-of-Thought 기반 알고리즘을 사용하여 문서 구조를 파악하고 LaTeX 코드로 변환합니다.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.files_data:
            st.warning("먼저 파일을 업로드해주세요.")
        else:
            # Select file to convert
            file_names = [data["filename"] for data in st.session_state.files_data]
            selected_file = st.selectbox(
                "변환할 파일 선택", 
                file_names,
                key="latex_file_select"
            )
            
            # Get file data
            file_data = next(data for data in st.session_state.files_data if data["filename"] == selected_file)
            
            # LaTeX template options
            template_type = st.radio(
                "LaTeX 템플릿 유형",
                ["report", "article"],
                horizontal=True,
                help="report는 장(chapter) 단위 구성을, article은 절(section) 단위 구성을 지원합니다."
            )
            
            # Project info input
            with st.expander("프로젝트 정보 입력", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    title = st.text_input("제목", value=file_data["metadata"]["properties"].get("title", "국책과제 보고서"))
                    author = st.text_input("저자", value=file_data["metadata"]["properties"].get("author", "연구책임자"))
                with col2:
                    abstract = st.text_area("초록", value="이 보고서는 국책과제의 연구 결과를 정리한 것입니다.", height=100)
                    keywords = st.text_input("키워드", value="국책과제, 연구, 보고서")
            
            # Convert button
            if st.button("LaTeX로 변환"):
                with st.spinner("HWP 파일을 LaTeX로 변환 중..."):
                    try:
                        # Initialize converter
                        converter = HwpToLatexConverter(api_key=st.session_state.api_key)
                        
                        # Project info
                        project_info = {
                            "title": title,
                            "author": author,
                            "abstract": abstract,
                            "keywords": keywords
                        }
                        
                        # Generate template if requested
                        if st.session_state.get("use_template", False):
                            latex_code = converter.generate_template(
                                template_type=template_type,
                                project_info=project_info
                            )
                            
                            # Store results
                            st.session_state.latex_results[selected_file] = {
                                "latex_code": latex_code,
                                "document_structure": None,
                                "template_type": template_type,
                                "project_info": project_info
                            }
                        else:
                            # Check if file content is available
                            if "file_content" not in file_data["metadata"] or not file_data["metadata"]["file_content"]:
                                st.error("파일 내용을 찾을 수 없습니다. 파일을 다시 업로드해주세요.")
                                return
                            
                            # Create temporary file
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".hwp") as temp_file:
                                temp_file.write(file_data["metadata"]["file_content"])
                                temp_file_path = temp_file.name
                            
                            try:
                                # Convert file
                                with open(temp_file_path, 'rb') as f:
                                    result = converter.convert_file(
                                        file_obj=f,
                                        template_type=template_type
                                    )
                                
                                # Store results
                                st.session_state.latex_results[selected_file] = {
                                    "latex_code": result["latex_code"],
                                    "document_structure": result["document_structure"],
                                    "template_type": template_type,
                                    "project_info": project_info
                                }
                            finally:
                                # Clean up temp file
                                if os.path.exists(temp_file_path):
                                    os.unlink(temp_file_path)
                        
                        st.success("LaTeX 변환이 완료되었습니다!")
                        
                    except Exception as e:
                        st.error(f"LaTeX 변환 중 오류가 발생했습니다: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            
            # Use template only option
            st.session_state.use_template = st.checkbox(
                "템플릿만 생성 (HWP 내용 변환 없음)", 
                value=st.session_state.get("use_template", False),
                help="체크하면 HWP 내용을 변환하지 않고 빈 템플릿만 생성합니다."
            )
            
            # Display conversion results if available
            if selected_file in st.session_state.latex_results:
                result = st.session_state.latex_results[selected_file]
                
                st.subheader("LaTeX 변환 결과")
                
                # Display LaTeX code
                st.code(result["latex_code"], language="latex")
                
                # Download button
                latex_code_bytes = result["latex_code"].encode()
                file_name = Path(selected_file).stem + ".tex"
                
                st.download_button(
                    label="LaTeX 파일 다운로드",
                    data=latex_code_bytes,
                    file_name=file_name,
                    mime="text/plain"
                )
                
                # Display document structure if available
                if result["document_structure"]:
                    with st.expander("문서 구조 정보", expanded=False):
                        st.json(result["document_structure"])
                
                # LaTeX tips
                with st.expander("LaTeX 사용 팁", expanded=False):
                    st.markdown("""
                    ### LaTeX 컴파일 방법
                    
                    1. 다운로드한 `.tex` 파일을 LaTeX 편집기(TeXstudio, Overleaf 등)에서 열기
                    2. 한글 지원을 위해 XeLaTeX 또는 LuaLaTeX 엔진으로 컴파일
                    3. 필요한 패키지가 설치되어 있는지 확인
                    
                    ### 유용한 LaTeX 리소스
                    
                    - [Overleaf 온라인 LaTeX 편집기](https://www.overleaf.com/)
                    - [LaTeX 튜토리얼](https://www.latex-tutorial.com/)
                    - [한글 LaTeX 사용 가이드](https://www.ktug.org/)
                    """)

    with tab4:
        st.markdown('<p class="sub-header">문서 비교</p>', unsafe_allow_html=True)
        
        # Check if we have at least 2 analyzed files
        analyzed_files = [
            data["filename"] for data in st.session_state.files_data 
            if data["filename"] in st.session_state.analysis_results
        ]
        
        if len(analyzed_files) < 2:
            st.warning("비교 분석을 위해서는 최소 2개 이상의 파일을 분석해야 합니다.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                file1 = st.selectbox("첫 번째 파일", analyzed_files, key="compare_file1")
            
            with col2:
                # Filter out the first selected file
                remaining_files = [f for f in analyzed_files if f != file1]
                file2 = st.selectbox("두 번째 파일", remaining_files, key="compare_file2")
            
            if st.button("비교 분석하기"):
                with st.spinner("비교 분석 중..."):
                    try:
                        # Get analysis results
                        results1 = st.session_state.analysis_results[file1]
                        results2 = st.session_state.analysis_results[file2]
                        
                        # Get file data
                        file_data1 = next(data for data in st.session_state.files_data if data["filename"] == file1)
                        file_data2 = next(data for data in st.session_state.files_data if data["filename"] == file2)
                        
                        # Generate comparison
                        comparison = hybrid_search.compare_projects(
                            project1={
                                "filename": file1,
                                "text": file_data1["text"],
                                "analysis": results1
                            },
                            project2={
                                "filename": file2,
                                "text": file_data2["text"],
                                "analysis": results2
                            }
                        )
                        
                        # Display comparison results
                        st.subheader("비교 분석 결과")
                        
                        # Create tabs for different comparison aspects
                        comparison_tabs = st.tabs(["주요 차이점", "유사점", "종합 평가"])
                        
                        with comparison_tabs[0]:
                            st.markdown(comparison["differences"])
                        
                        with comparison_tabs[1]:
                            st.markdown(comparison["similarities"])
                        
                        with comparison_tabs[2]:
                            st.markdown(comparison["evaluation"])
                        
                    except Exception as e:
                        st.error(f"비교 분석 중 오류가 발생했습니다: {str(e)}")

    with tab5:
        st.markdown('<p class="sub-header">질의응답</p>', unsafe_allow_html=True)
        
        if not st.session_state.files_data:
            st.warning("먼저 파일을 업로드하고 분석해주세요.")
        else:
            # Select analyzed file
            analyzed_files = [
                data["filename"] for data in st.session_state.files_data 
                if data["filename"] in st.session_state.analysis_results
            ]
            
            if not analyzed_files:
                st.warning("먼저 파일을 분석해주세요.")
            else:
                selected_file = st.selectbox(
                    "질의응답할 파일 선택", 
                    analyzed_files,
                    key="qa_file_select"
                )
                
                # Get file data
                file_data = next(data for data in st.session_state.files_data if data["filename"] == selected_file)
                results = st.session_state.analysis_results[selected_file]
                
                # 고급 질의응답 모드 선택
                qa_mode = st.radio(
                    "질의응답 모드",
                    ["기본 모드", "고급 모드"],
                    key="qa_mode",
                    horizontal=True
                )
                
                # 심층 분석 결과 활용 여부
                use_deep_analysis = False
                deep_analysis_results = None
                
                if qa_mode == "고급 모드":
                    use_deep_analysis = st.checkbox("심층 분석 결과 활용", value=True)
                    
                    if use_deep_analysis and "deep_analysis_results" in st.session_state and selected_file in st.session_state.deep_analysis_results:
                        deep_analysis_results = st.session_state.deep_analysis_results[selected_file]
                    elif use_deep_analysis:
                        st.info("심층 분석 결과가 없습니다. '심층 분석' 탭에서 먼저 심층 분석을 수행해주세요.")
                
                # Display chat history
                st.subheader("질의응답")
                
                # Filter chat history for the selected file
                file_chat_history = [
                    msg for msg in st.session_state.chat_history 
                    if msg["file"] == selected_file
                ]
                
                for msg in file_chat_history:
                    if msg["role"] == "user":
                        st.markdown(f"""
                        <div style='background-color: #E3F2FD; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                            <p><strong>질문:</strong> {msg["content"]}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background-color: #F5F5F5; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                            <p><strong>AI 응답:</strong> {msg["content"]}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # User input
                user_question = st.text_input("국책과제에 대해 질문하세요", key="user_question")
                
                if st.button("질문하기"):
                    if user_question:
                        # Add user question to chat history
                        st.session_state.chat_history.append({
                            "role": "user",
                            "content": user_question,
                            "file": selected_file
                        })
                        
                        with st.spinner("답변 생성 중..."):
                            try:
                                if qa_mode == "기본 모드":
                                    # 기본 질의응답
                                    answer = hybrid_search.generate_answer(
                                        question=user_question,
                                        context=file_data["text"],
                                        analysis_results=results,
                                        use_cot=True,
                                        expert_mode=st.session_state.expert_mode
                                    )
                                    
                                    # Add answer to chat history
                                    st.session_state.chat_history.append({
                                        "role": "assistant",
                                        "content": answer,
                                        "file": selected_file
                                    })
                                else:
                                    # 고급 질의응답
                                    qa_result = hybrid_search.generate_advanced_qa(
                                        question=user_question,
                                        project_text=file_data["text"],
                                        analysis_results=results,
                                        deep_analysis_results=deep_analysis_results
                                    )
                                    
                                    # Add answer to chat history
                                    st.session_state.chat_history.append({
                                        "role": "assistant",
                                        "content": qa_result["answer"],
                                        "file": selected_file
                                    })
                                    
                                    # 추론 과정 표시 (접을 수 있는 섹션)
                                    if "reasoning" in qa_result and qa_result["reasoning"]:
                                        with st.expander("추론 과정", expanded=False):
                                            st.markdown(qa_result["reasoning"])
                                
                                # Rerun to display the new messages
                                st.experimental_rerun()
                                
                            except Exception as e:
                                st.error(f"답변 생성 중 오류가 발생했습니다: {str(e)}")

    # 최신성 검사 탭
    with tab6:
        st.subheader("HWP 문서 최신성 검사")
        st.markdown("""
        이 기능은 HWP 문서의 내용과 메타데이터를 분석하여 최신 정보와 비교하고, 
        업데이트가 필요한 부분을 식별합니다. Perplexity API를 사용하여 실시간 웹 검색을 수행합니다.
        """)
        
        if not st.session_state.files_data:
            st.info("먼저 파일을 업로드해주세요.")
        else:
            # 파일 선택 (드롭다운)
            file_options = [file_data["filename"] for file_data in st.session_state.files_data]
            selected_file = st.selectbox("분석할 파일 선택", file_options, key="freshness_file_select")
            
            # 선택한 파일 데이터 가져오기
            selected_file_data = None
            for file_data in st.session_state.files_data:
                if file_data["filename"] == selected_file:
                    selected_file_data = file_data
                    break
            
            if selected_file_data:
                # 메타데이터 표시
                with st.expander("파일 메타데이터", expanded=True):
                    if "metadata" in selected_file_data:
                        metadata = selected_file_data["metadata"]
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**제목:**", metadata.get("제목", "알 수 없음"))
                            st.write("**작성자:**", metadata.get("작성자", "알 수 없음"))
                        with col2:
                            st.write("**생성일자:**", metadata.get("생성일자", "알 수 없음"))
                            st.write("**수정일자:**", metadata.get("수정일자", "알 수 없음"))
                    else:
                        st.warning("이 파일에 대한 메타데이터를 찾을 수 없습니다.")
                
                # 최신성 검사 실행 버튼
                if st.button("최신성 검사 실행", key="run_freshness_check"):
                    if not st.session_state.api_key:
                        st.error("Google Gemini API 키가 설정되지 않았습니다. 사이드바에서 API 키를 설정해주세요.")
                    elif not st.session_state.perplexity_connected:
                        st.error("Perplexity API가 연결되지 않았습니다. 사이드바에서 API 키를 설정하고 연결 테스트를 진행해주세요.")
                    else:
                        with st.spinner("문서 최신성 검사 중... 이 작업은 최대 1분 정도 소요될 수 있습니다."):
                            try:
                                # 하이브리드 검색 엔진 초기화
                                hybrid_engine = HybridSearchEngine(
                                    st.session_state.api_key,
                                    st.session_state.perplexity_api_key
                                )
                                
                                # 최신성 검사 실행
                                freshness_result = cached_check_hwp_content_freshness(
                                    hybrid_engine,
                                    selected_file_data["text"],
                                    selected_file_data.get("metadata", {})
                                )
                                
                                if "error" in freshness_result:
                                    st.error(f"최신성 검사 중 오류가 발생했습니다: {freshness_result['error']}")
                                else:
                                    # 세션 상태에 결과 저장
                                    if "freshness_results" not in st.session_state:
                                        st.session_state.freshness_results = {}
                                    
                                    st.session_state.freshness_results[selected_file] = freshness_result
                                    
                                    # 업데이트 제안 생성
                                    update_suggestions = cached_suggest_updates(
                                        hybrid_engine,
                                        selected_file_data["text"],
                                        freshness_result
                                    )
                                    
                                    if "error" not in update_suggestions:
                                        st.session_state.freshness_results[selected_file]["update_suggestions"] = update_suggestions
                                    
                                    st.success("최신성 검사가 완료되었습니다!")
                            
                            except Exception as e:
                                st.error(f"최신성 검사 중 오류가 발생했습니다: {str(e)}")
                                logging.error(f"최신성 검사 오류: {str(e)}")
                
                # 검사 결과 표시
                if "freshness_results" in st.session_state and selected_file in st.session_state.freshness_results:
                    result = st.session_state.freshness_results[selected_file]
                    
                    st.subheader("최신성 검사 결과")
                    
                    # 최신성 평가 표시
                    with st.expander("최신성 평가", expanded=True):
                        if "freshness_evaluation" in result:
                            st.markdown(result["freshness_evaluation"])
                        else:
                            st.warning("최신성 평가 결과를 찾을 수 없습니다.")
                    
                    # 최신 정보 표시
                    with st.expander("관련 최신 정보", expanded=True):
                        if "latest_info" in result:
                            st.markdown(result["latest_info"])
                        else:
                            st.warning("관련 최신 정보를 찾을 수 없습니다.")
                    
                    # 업데이트 제안 표시
                    with st.expander("업데이트 제안사항", expanded=True):
                        if "update_suggestions" in result:
                            if isinstance(result["update_suggestions"], dict) and "update_suggestions" in result["update_suggestions"]:
                                st.markdown(result["update_suggestions"]["update_suggestions"])
                            elif isinstance(result["update_suggestions"], str):
                                st.markdown(result["update_suggestions"])
                            else:
                                st.warning("업데이트 제안사항 형식을 해석할 수 없습니다.")
                        else:
                            st.warning("업데이트 제안사항을 찾을 수 없습니다.")
                    
                    # 결과 저장 버튼
                    if st.button("결과 저장", key="save_freshness_results"):
                        try:
                            # 결과를 JSON 파일로 저장
                            results_dir = "data/results"
                            os.makedirs(results_dir, exist_ok=True)
                            
                            file_name = f"{os.path.splitext(selected_file)[0]}_freshness_check.json"
                            file_path = os.path.join(results_dir, file_name)
                            
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                            
                            st.success(f"결과가 저장되었습니다: {file_path}")
                        
                        except Exception as e:
                            st.error(f"결과 저장 중 오류가 발생했습니다: {str(e)}")
                            logging.error(f"결과 저장 오류: {str(e)}")

if __name__ == "__main__":
    main() 