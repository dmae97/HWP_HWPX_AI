# Streamlit 클라우드 배포 가이드

이 문서는 HWP & HWPX 파일 분석기를 Streamlit 클라우드에 배포하기 위한 가이드입니다.

## 1. Streamlit Cloud 시크릿 설정

Streamlit Cloud에서는 환경 변수 대신 시크릿을 사용합니다. 다음은 시크릿 설정 방법입니다:

1. Streamlit Cloud 대시보드에서 앱을 선택합니다.
2. "설정(Settings)" > "시크릿(Secrets)"을 클릭합니다.
3. 다음과 같은 형식으로 시크릿을 추가합니다:

```toml
GOOGLE_API_KEY = "your_google_api_key"
PERPLEXITY_API_KEY = "your_perplexity_api_key"
```

## 2. 리소스 관리

Streamlit Cloud는 기본적으로 다음과 같은 리소스 제한이 있습니다:

- 메모리: 1GB (무료 티어)
- 스토리지: 제한적
- 타임아웃: 10분 (무료 티어)

이러한 제한을 고려하여 다음과 같이 최적화할 수 있습니다:

- 큰 파일 처리 시 메모리 사용량을 모니터링하고 제한합니다.
- 캐시를 적극적으로 활용하여 API 호출을 최소화합니다.
- 분석 결과는 Streamlit의 캐싱 기능을 사용하여 저장합니다.

## 3. 성능 최적화

### API 호출 최적화
- 가능한 경우 `@st.cache_data`를 사용하여 API 호출 결과를 캐시합니다.
- 병렬 처리를 적절히 조절하여 Streamlit 리소스를 초과하지 않도록 합니다.

```python
@st.cache_data(ttl=3600)  # 1시간 동안 캐시
def cached_api_call(prompt):
    # API 호출 코드
    return result
```

### 대용량 파일 처리
- 대용량 HWP/HWPX 파일은 청크 단위로 처리합니다.
- 이미지 추출 시 리사이즈 옵션을 제공하여 메모리 사용량을 줄입니다.

## 4. 고려해야 할 사항

### 파일 업로드 제한
- Streamlit Cloud에서는 기본적으로 업로드 파일 크기에 제한이 있습니다.
- 크기 제한: 무료 티어 기준 약 200MB
- UI에 파일 크기 제한을 명시하고, 크기가 큰 파일을 업로드할 경우 사용자에게 알립니다.

### 타임아웃 처리
- 무료 티어의 10분 타임아웃을 고려하여 긴 작업을 더 작은 단위로 분할합니다.
- 장시간 실행되는 분석의 경우 사용자에게 진행 상황을 표시합니다.

### 네트워크 요청
- API 호출 타임아웃을 적절히 설정하고 재시도 로직을 구현합니다.
- 네트워크 오류 발생 시 사용자에게 명확한 오류 메시지를 제공합니다.

## 5. 배포 체크리스트

- [ ] requirements.txt 파일이 모든 필요한 패키지를 포함하는지 확인
- [ ] API 키가 Streamlit Cloud 시크릿에 설정되었는지 확인
- [ ] 임시 파일 정리 코드 추가 (파일 업로드 후 처리 완료된 임시 파일 삭제)
- [ ] 메모리 사용량이 제한 내에 있는지 테스트
- [ ] 오류 처리 및 로깅 확인
- [ ] 대용량 파일 처리 시 타임아웃 처리 확인
- [ ] 모바일 및 데스크톱 화면에서의 UI 테스트

## 6. 문제 해결

### 메모리 오류
```
MemoryError: ...
```
- 파일 크기 제한 설정
- 청크 단위 처리 구현
- 불필요한 데이터 정리

### 타임아웃 오류
```
TimeoutError: ...
```
- 장시간 작업을 더 작은 단위로 분할
- 프로그레스 바로 사용자에게 진행 상황 표시

### 모듈 임포트 오류
```
ModuleNotFoundError: ...
```
- requirements.txt 업데이트
- Python 버전 확인 (Streamlit Cloud는 Python 3.7, 3.8, 3.9, 3.10 지원)

## 7. 유용한 명령어

### Streamlit 로컬 실행
```bash
streamlit run app.py
```

### requirements.txt 생성
```bash
pip freeze > requirements.txt
```

### 가상환경 설정
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## 8. 참고 자료

- [Streamlit 공식 배포 가이드](https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app)
- [Streamlit 시크릿 관리](https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)
- [Streamlit 캐싱](https://docs.streamlit.io/library/advanced-features/caching) 