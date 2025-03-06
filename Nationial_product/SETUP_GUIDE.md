# 국책과제 Expert AI 설치 가이드

이 가이드는 국책과제 Expert AI 시스템을 설치하고 실행하는 방법을 안내합니다.

## 1. 가상환경 설정 및 패키지 설치

### Windows 환경

1. 제공된 배치 파일을 실행하여 가상환경을 설정하고 필요한 패키지를 설치합니다:
   ```
   install_packages.bat
   ```

2. 가상환경을 활성화합니다:
   ```
   activate_venv.bat
   ```

### Linux/Mac 환경

1. 설치 스크립트에 실행 권한을 부여합니다:
   ```
   chmod +x install_packages.sh activate_venv.sh
   ```

2. 설치 스크립트를 실행합니다:
   ```
   ./install_packages.sh
   ```

3. 가상환경을 활성화합니다:
   ```
   source activate_venv.sh
   ```

## 2. API 키 설정

1. `.env.example` 파일을 `.env`로 복사합니다:
   - Windows: `copy .env.example .env`
   - Linux/Mac: `cp .env.example .env`

2. 텍스트 편집기로 `.env` 파일을 열고 실제 API 키를 입력합니다:
   ```
   GOOGLE_API_KEY=your_actual_google_api_key
   PERPLEXITY_API_KEY=your_actual_perplexity_api_key
   ```

## 3. 애플리케이션 실행

가상환경이 활성화된 상태에서 다음 명령어를 실행합니다:
```
streamlit run app.py
```

## 4. 주요 기능 안내

국책과제 Expert AI는 다음과 같은 주요 기능을 제공합니다:

### 파일 분석
- HWP 파일 업로드 및 텍스트 추출
- 국책과제 문서 기본 분석 (목적, 배경, 주요 내용, 예산, 기간, 참여 기관, 기대 효과 등)
- 다양한 분석 방법 지원 (표준, CoT, RL, 하이브리드)
- 검증 및 개선 과정을 통한 분석 품질 향상
- 최신 정보 통합 분석 (하이브리드 검색 활용)

### 질의응답
- 국책과제 문서에 대한 질문 및 답변
- 기본 모드와 고급 모드 지원
- 심층 분석 결과를 활용한 고급 질의응답
- 추론 과정 확인 가능

### 심층 분석
- 국책과제의 다양한 측면에 대한 심층적인 분석
- 분석 초점 영역 선택 가능 (전체, 예산, 기술적 타당성, 시장성)
- 분석 결과 다운로드 지원

### 비교 분석
- 두 국책과제 간의 비교 분석
- 주요 차이점, 유사점, 종합 평가 제공

### LaTeX 변환
- HWP 파일을 LaTeX 형식으로 변환
- 문서 구조 보존 및 수식 변환 지원

## 5. 문제 해결

### 가져오기 오류 해결

가져오기 오류가 발생하는 경우, 다음 명령어로 필요한 패키지가 올바르게 설치되었는지 확인하세요:
```
pip list
```

누락된 패키지가 있다면 다음 명령어로 설치할 수 있습니다:
```
pip install 패키지명
```

주요 패키지 목록:
- pyhwpx==0.44.1
- langchain==0.3.19
- langchain-google-genai==2.0.11
- streamlit==1.32.0
- python-dotenv==1.0.0
- google-generativeai==0.4.0
- pandas==2.2.0
- requests==2.31.0
- pywin32==308 (Windows 환경만 해당)
- openai==1.1.0
- langchain-anthropic==0.2.1
- langchain-openai==0.2.1
- langchain-community==0.2.1
- langchain-core==0.2.1

### Windows에서 COM 초기화 관련 오류

Windows 환경에서 `CoInitialize가 호출되지 않았습니다` 오류가 발생하는 경우:

1. `hwp_utils.py` 파일에서 COM 초기화 코드가 제대로 구현되어 있는지 확인하세요:
   ```python
   import pythoncom
   
   # COM 초기화 코드
   pythoncom.CoInitialize()
   # 작업 수행
   # ...
   # COM 정리
   pythoncom.CoUninitialize()
   ```

2. pywin32를 재설치해보세요:
   ```
   pip uninstall pywin32
   pip install pywin32==308
   ```

3. 관리자 권한으로 명령 프롬프트를 실행한 후 다음 명령어를 실행하세요:
   ```
   python -m pip install --upgrade pywin32
   python -m pywin32_postinstall -install
   ```

### pyhwpx 관련 오류

`pyhwpx` 관련 오류가 발생하는 경우:

1. 정확한 버전으로 재설치해보세요:
   ```
   pip uninstall pyhwpx
   pip install pyhwpx==0.44.1
   ```

2. `module 'pyhwpx' has no attribute 'HwpFile'` 또는 `module 'pyhwpx' has no attribute 'open'` 오류가 발생하는 경우, API 변경 사항을 확인하고 코드를 업데이트하세요. 최신 버전의 pyhwpx는 다른 메서드를 사용할 수 있습니다.

3. 한글(HWP)이 설치되어 있는지 확인하세요. pyhwpx는 한글 프로그램이 설치되어 있어야 정상적으로 작동합니다.

### API 키 관련 오류

1. `.env` 파일에 API 키가 올바르게 설정되어 있는지 확인하세요.

2. Perplexity API 모델 이름 오류가 발생하는 경우, 지원되는 모델 이름으로 변경하세요. 최신 지원 모델은 [Perplexity API 문서](https://docs.perplexity.ai/guides/model-cards)에서 확인할 수 있습니다.

3. Google Gemini API 오류가 발생하는 경우, API 키가 유효한지 확인하고 할당량 초과 여부를 확인하세요.

### Streamlit 관련 오류

1. Streamlit 버전이 최신인지 확인하세요:
   ```
   pip install --upgrade streamlit
   ```

2. `st.experimental_rerun` 관련 경고가 표시되는 경우, `st.rerun`으로 변경하세요.

3. 포트 충돌이 발생하는 경우, 다른 포트를 지정하여 실행하세요:
   ```
   streamlit run app.py --server.port=8501
   ```

## 6. 테스트

설치가 완료되면 다음 명령어로 기능을 테스트할 수 있습니다:

### HWP 파일 처리 테스트
```
python test_hwp.py 경로/파일명.hwp
```

### API 연결 테스트
```
python test_api.py
```

## 7. 도움말 및 문의

추가 도움이 필요하면 README.md 파일을 참조하거나 개발팀에 문의하세요.

## 8. 업데이트 내역

### 최신 업데이트 (2025-03-04)
- 심층 분석 기능 추가
- 고급 질의응답 기능 개선
- 비교 분석 기능 강화
- HWP 파일 처리 안정성 개선
- UI/UX 개선

© 2025 유근빈 Yu-GeunBin 