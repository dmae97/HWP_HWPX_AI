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

## Railway 배포 시 secrets.toml 설정

Streamlit 앱은 API 키와 같은 비밀 정보를 `.streamlit/secrets.toml` 파일에 저장합니다. Railway에서 배포할 때는 다음과 같이 이 파일을 처리할 수 있습니다:

### 방법 1: 환경 변수 사용 (권장)

Railway 대시보드에서 환경 변수를 직접 설정합니다:

1. Railway 프로젝트로 이동
2. Variables 탭 선택
3. 다음 변수 추가:
   - `GOOGLE_API_KEY`: Google API 키 값
   - `PERPLEXITY_API_KEY`: Perplexity API 키 값
   - `STREAMLIT_SECRETS_PATH`: `/app/.streamlit/secrets.toml`

### 방법 2: secrets.toml 파일 포함하기

1. `.streamlit/secrets.toml` 파일을 생성하고 API 키 입력:
```toml
# Streamlit Secrets
GOOGLE_API_KEY = "your-google-api-key"
PERPLEXITY_API_KEY = "your-perplexity-api-key"
```

2. Railway 프로젝트에 이 파일이 포함되도록 합니다.

### 주의사항

* API 키와 같은 중요 정보는 GitHub에 커밋하지 마세요.
* Railway 환경 변수를 사용하는 것이 가장 안전한 방법입니다.
* `.gitignore` 파일에 `.streamlit/secrets.toml`을 추가하여 실수로 커밋되지 않도록 합니다. 

## 웹 주소 및 포트폴리오 사용

Railway는 각 배포에 고유한 웹 주소(URL)를 자동으로 제공합니다. 이는 다음과 같이 확인하고 관리할 수 있습니다:

### 기본 도메인 확인하기

1. Railway 대시보드에서 프로젝트를 선택합니다.
2. "Settings" 탭으로 이동하여 "Domains" 섹션을 확인합니다.
3. 자동 생성된 도메인(예: `your-app-name.up.railway.app`)을 확인할 수 있습니다.

### 커스텀 도메인 설정하기

포트폴리오용으로 더 전문적인 URL이 필요하다면:

1. "Settings" 탭의 "Domains" 섹션으로 이동합니다. 
2. "Custom Domain" 옵션을 선택합니다.
3. 소유한 도메인을 입력하고 DNS 설정을 완료합니다.

### 보안 및 공개 설정

Railway에 배포된 앱은 기본적으로 인터넷에 공개되어 있습니다. 포트폴리오 용도로는 이상적이지만, API 키와 같은 민감한 정보는 환경 변수로 관리해야 합니다.

### 앱 접근 제한

특정 IP만 접근 가능하도록 제한하려면 Railway Pro 플랜으로 업그레이드해야 합니다:

1. Railway Pro로 업그레이드합니다.
2. "Settings" > "Network" 섹션에서 IP 허용 목록을 설정합니다. 