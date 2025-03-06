# Railway 배포 가이드

이 문서는 HWP & HWPX 파일 분석기를 Railway에 배포하기 위한 가이드입니다.

## 1. Railway 계정 설정

1. [Railway 웹사이트](https://railway.app/)에 접속하고 계정을 생성하거나 로그인합니다.
2. GitHub 계정으로 로그인하는 것이 가장 편리합니다.

## 2. 새 프로젝트 생성

1. Railway 대시보드에서 "New Project" 버튼을 클릭합니다.
2. "Deploy from GitHub repo"를 선택합니다.
3. 배포하려는 GitHub 저장소(hwp_hwpx_ai)를 선택합니다.

## 3. 환경 변수 설정

1. 프로젝트가 생성되면 "Variables" 탭으로 이동합니다.
2. 다음 환경 변수를 추가합니다:
   - `GOOGLE_API_KEY`: Gemini API 키
   - `PERPLEXITY_API_KEY`: Perplexity API 키 (선택 사항)

## 4. 배포 설정

Railway는 자동으로 프로젝트 루트의 `railway.toml` 파일을 감지하여 배포 설정을 로드합니다. 이 파일에는 다음과 같은 설정이 포함되어 있습니다:

```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 3

[env]
PORT = "8501"
```

## 5. 리소스 설정

1. "Settings" 탭으로 이동합니다.
2. "Resources" 섹션에서 애플리케이션에 필요한 리소스를 구성합니다:
   - 메모리: 최소 512MB (가능하면 1GB 이상 권장)
   - CPU: 0.5 vCPU 이상 권장
   - 디스크: 기본값 (1GB) 사용

## 6. 도메인 설정 (선택 사항)

1. "Settings" 탭의 "Domains" 섹션으로 이동합니다.
2. "Generate Domain" 버튼을 클릭하여 기본 도메인을 생성하거나 커스텀 도메인을 설정합니다.

## 7. 파일 크기 제한 설정

Railway에서는 Streamlit Cloud보다 더 큰 파일을 처리할 수 있지만, 여전히 리소스 제한이 있습니다. 애플리케이션에서 파일 크기 제한을 설정하는 것이 좋습니다:

- 일반 모드: 최대 50MB
- 메모리 최적화 모드: 최대 200MB

## 8. 배포 모니터링

1. "Deployments" 탭에서 배포 상태와 로그를 모니터링할 수 있습니다.
2. 배포가 실패한 경우 로그를 확인하여 문제를 해결합니다.

## 9. 주의 사항

### Windows 종속성 처리

이 애플리케이션은 Windows 환경에서 최적의 기능을 제공하지만, Railway(Linux)에서도 제한된 기능으로 실행됩니다:

- **텍스트 추출**: 제한적으로 지원 (일부 텍스트만 추출 가능)
- **이미지 추출**: 지원되지 않음
- **메타데이터**: 기본 정보만 추출
- **표 추출**: 지원되지 않음

### Railway 비용 관리

- Railway는 무료 크레딧을 제공하지만, 사용량이 많아지면 비용이 발생할 수 있습니다.
- 프로젝트 설정에서 "Billing" 탭을 통해 비용을 모니터링하세요.
- 무료 크레딧이 모두 소진된 경우 서비스가 중지될 수 있습니다.

## 10. 지속적 배포

Railway는 GitHub 저장소와 연결되어 있어 `main` 브랜치에 변경 사항을 커밋하면 자동으로 새 버전이 배포됩니다. 이렇게 하면 항상 최신 코드가 실행됩니다.

## 11. 문제 해결

### 배포 실패

```
Build failed: ...
```
- `requirements.txt` 파일에 오류가 있는지 확인합니다.
- Python 버전 호환성 문제가 있는지 확인합니다.

### 메모리 오류

```
MemoryError: ...
```
- Railway 대시보드에서 메모리 할당량을 늘립니다.
- 애플리케이션의 메모리 최적화 모드를 활성화합니다.

### 환경 변수 오류

```
API key not found: ...
```
- Railway 대시보드에서 모든 필요한 환경 변수가 올바르게 설정되었는지 확인합니다.

## 12. 참고 자료

- [Railway 공식 문서](https://docs.railway.app/)
- [Railway CLI 사용 방법](https://docs.railway.app/develop/cli)
- [Railway 가격 정책](https://docs.railway.app/reference/pricing) 