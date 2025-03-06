@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo 디버그: 스크립트 시작됨

REM 현재 디렉토리를 기본 대상으로 설정
set "TARGET_DIR=%CD%"

REM 명령줄 인수가 제공된 경우 해당 디렉토리를 사용
if not "%~1"=="" (
    set "TARGET_DIR=%~1"
)

echo 디버그: 대상 디렉토리 = %TARGET_DIR%

REM .cursor\rules 폴더를 대상 디렉토리에 확실히 생성
echo 📁 .cursor\rules 폴더 생성 중...
if not exist "%TARGET_DIR%\.cursor\" (
    mkdir "%TARGET_DIR%\.cursor"
    echo - .cursor 폴더 생성됨
)
if not exist "%TARGET_DIR%\.cursor\rules\" (
    mkdir "%TARGET_DIR%\.cursor\rules"
    echo - .cursor\rules 폴더 생성됨
)

REM 경로 설정
set "ORIGINAL_FILES_DIR=D:\cursor-auto-rules-agile-workflow\korean"
echo 원본 파일 경로: %ORIGINAL_FILES_DIR%

REM 원본 파일 복사 시도
echo 🔄 원본 파일을 Cursor 규칙으로 복사 시도 중...
set "FILES_COPIED=0"

REM 필수 파일들의 목록과 해당 내용
echo 📄 필수 규칙 파일 생성 중...

REM 801-workflow-agile.mdc 파일 생성
echo ^# 애자일 워크플로우: 사용자 프로젝트나 목표를 완수하기 위한 단계별 과정 > "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^## 중요 규칙 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^- .ai/prd.md 파일이 존재하고 승인되어야 함 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^- 이 워크플로우는 메모리 시스템에 중요함 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^- 문서를 잘 작성하는 것이 중요함 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^- 각 단계를 순서대로 따라야 함 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo ^- 한 번에 하나의 에픽과 스토리만 진행 중이어야 함 >> "%TARGET_DIR%\.cursor\rules\801-workflow-agile.mdc"
echo - 801-workflow-agile.mdc 파일 생성됨

REM 901-prd-template.mdc 파일 생성
echo ^# PRD(제품 요구사항 문서) 템플릿 표준 > "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo ^## 요구사항 >> "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo ^- 표준화된 PRD 구조를 따라야 함 >> "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo ^- 모든 필수 섹션이 포함되어야 함 >> "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo ^- 문서는 적절한 계층 구조를 가져야 함 >> "%TARGET_DIR%\.cursor\rules\901-prd-template.mdc"
echo - 901-prd-template.mdc 파일 생성됨

REM 902-arch-template.mdc 파일 생성
echo ^# 아키텍처 문서 표준 > "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo ^## 요구사항 >> "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo ^- 아키텍처 결정은 명확하게 문서화되어야 함 >> "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo ^- 기술 스택과 관련 정보가 포함되어야 함 >> "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo ^- 변경 내역이 추적되어야 함 >> "%TARGET_DIR%\.cursor\rules\902-arch-template.mdc"
echo - 902-arch-template.mdc 파일 생성됨

REM 903-story-template.mdc 파일 생성
echo ^# 스토리 템플릿 표준 > "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo ^## 요구사항 >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo ^- 표준화된 스토리 구조를 따라야 함 >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo ^- 모든 필수 섹션이 포함되어야 함 >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo ^- 작업 및 하위 작업이 명확하게 정의되어야 함 >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo ^- 진행 상황이 정확하게 추적되어야 함 >> "%TARGET_DIR%\.cursor\rules\903-story-template.mdc"
echo - 903-story-template.mdc 파일 생성됨

REM git-push-command.mdc 파일 생성
echo ^# Git 푸시 명령어 표준 > "%TARGET_DIR%\.cursor\rules\git-push-command.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\git-push-command.mdc"
echo ^## 요구사항 >> "%TARGET_DIR%\.cursor\rules\git-push-command.mdc"
echo ^- 일관된 커밋 메시지 형식을 사용해야 함 >> "%TARGET_DIR%\.cursor\rules\git-push-command.mdc"
echo ^- 변경 사항을 명확하게 설명해야 함 >> "%TARGET_DIR%\.cursor\rules\git-push-command.mdc"
echo - git-push-command.mdc 파일 생성됨

REM project-idea-prompt.mdc 파일 생성
echo ^# 프로젝트 아이디어 프롬프트 > "%TARGET_DIR%\.cursor\rules\project-idea-prompt.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\project-idea-prompt.mdc"
echo 새로운 프로젝트 아이디어를 시작할 때 사용하는 프롬프트 템플릿입니다. >> "%TARGET_DIR%\.cursor\rules\project-idea-prompt.mdc"
echo - project-idea-prompt.mdc 파일 생성됨

REM workflow-agile.mdc 파일 생성  
echo ^# 애자일 워크플로우 프로세스 > "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo ^## 워크플로우 단계 >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo ^1. 계획 단계 - PRD 및 아키텍처 문서 작성 >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo ^2. 구현 단계 - 스토리 및 작업 실행 >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo ^3. 검증 단계 - 테스트 및 검증 >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo ^4. 배포 단계 - 완료 및 릴리즈 >> "%TARGET_DIR%\.cursor\rules\workflow-agile.mdc"
echo - workflow-agile.mdc 파일 생성됨

REM template-arch.mdc 파일 생성
echo ^# 아키텍처 문서 템플릿 > "%TARGET_DIR%\.cursor\rules\template-arch.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\template-arch.mdc"
echo ^## 개요 >> "%TARGET_DIR%\.cursor\rules\template-arch.mdc"
echo 이 문서는 프로젝트의 아키텍처를 설명합니다. >> "%TARGET_DIR%\.cursor\rules\template-arch.mdc"
echo - template-arch.mdc 파일 생성됨

REM template-prd.mdc 파일 생성
echo ^# PRD 템플릿 > "%TARGET_DIR%\.cursor\rules\template-prd.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\template-prd.mdc"
echo ^## 개요 >> "%TARGET_DIR%\.cursor\rules\template-prd.mdc"
echo 이 문서는 제품 요구사항을 정의합니다. >> "%TARGET_DIR%\.cursor\rules\template-prd.mdc"
echo - template-prd.mdc 파일 생성됨

REM template-story.mdc 파일 생성
echo ^# 스토리 템플릿 > "%TARGET_DIR%\.cursor\rules\template-story.mdc"
echo. >> "%TARGET_DIR%\.cursor\rules\template-story.mdc"
echo ^## 개요 >> "%TARGET_DIR%\.cursor\rules\template-story.mdc"
echo 이 문서는 사용자 스토리를 정의합니다. >> "%TARGET_DIR%\.cursor\rules\template-story.mdc"
echo - template-story.mdc 파일 생성됨

REM 이제 원본 파일 복사 시도 (덮어쓰기로 진행)
if exist "%ORIGINAL_FILES_DIR%" (
    echo 원본 폴더에서 파일 복사 시도 중...
    set "FILE_LIST=801-workflow-agile.md 901-prd-template.md 902-arch-template.md 903-story-template.md git-push-command.md project-idea-prompt.md template-arch.md template-prd.md template-story.md workflow-agile.md"

    for %%f in (%FILE_LIST%) do (
        if exist "%ORIGINAL_FILES_DIR%\%%f" (
            echo - 원본 파일 발견: %%f
            set "mdcfile=%%~nf.mdc"
            copy "%ORIGINAL_FILES_DIR%\%%f" "%TARGET_DIR%\.cursor\rules\!mdcfile!" >nul
            if !errorlevel! equ 0 (
                echo - %%f 를 .cursor\rules\!mdcfile!로 복사 완료
                set /a FILES_COPIED+=1
            ) else (
                echo - %%f 복사 실패 (오류 코드: !errorlevel!)
            )
        )
    )
) else (
    echo 원본 폴더를 찾을 수 없습니다: %ORIGINAL_FILES_DIR%
)

REM 대상 디렉토리가 존재하는지 확인하고, README.md 초기화
if not exist "%TARGET_DIR%\" (
    echo 📁 새 프로젝트 디렉토리 생성 중: %TARGET_DIR%
    mkdir "%TARGET_DIR%"
    (
        echo # 새 프로젝트
        echo,
        echo 이 프로젝트는 [cursor-auto-rules-agile-workflow](https://github.com/bmadcode/cursor-auto-rules-agile-workflow)에서 구성된 애자일 워크플로우 지원 및 자동 규칙 생성으로 초기화되었습니다.
        echo,
        echo 워크플로우 문서는 [워크플로우 규칙](docs/workflow-rules.md)을 참조하세요.
    ) > "%TARGET_DIR%\README.md"
)

REM docs 폴더 생성 및 workflow-rules.md 문서 생성
echo 📝 docs 폴더 생성 중...
if not exist "%TARGET_DIR%\docs\" (
    mkdir "%TARGET_DIR%\docs"
    echo - docs 폴더 생성됨
)
(
    echo # Cursor 워크플로우 규칙
    echo,
    echo 이 프로젝트는 [cursor-auto-rules-agile-workflow](https://github.com/bmadcode/cursor-auto-rules-agile-workflow)의 자동 규칙 생성기를 사용하도록 업데이트되었습니다.
    echo,
    echo ^> **참고**: 이 스크립트는 템플릿 규칙을 최신 버전으로 업데이트하기 위해 언제든지 안전하게 다시 실행할 수 있습니다^. 생성한 사용자 지정 규칙에는 영향을 주거나 덮어쓰지 않습니다^.
    echo,
    echo ## 핵심 기능
    echo,
    echo - 자동화된 규칙 생성
    echo - 표준화된 문서 형식
    echo - AI 동작 제어 및 최적화
    echo - 유연한 워크플로우 통합 옵션
    echo,
    echo ## 워크플로우 통합 옵션
    echo,
    echo ### 1^. 자동 규칙 적용 (권장)
    echo 핵심 워크플로우 규칙은 ^.cursor/rules/에 자동으로 설치됩니다:
    echo - `901-prd^.mdc` - 제품 요구사항 문서 표준
    echo - `902-arch^.mdc` - 아키텍처 문서 표준
    echo - `903-story^.mdc` - 사용자 스토리 표준
    echo - `801-workflow-agile^.mdc` - 완전한 애자일 워크플로우 (선택 사항)
    echo,
    echo 이러한 규칙은 해당 파일 유형으로 작업할 때 자동으로 적용됩니다^.
    echo,
    echo ### 2^. 메모장 기반 워크플로우
    echo 더 유연한 접근 방식을 위해 `xnotes/`의 템플릿을 사용하세요:
    echo 1^. Cursor 옵션에서 메모장 활성화
    echo 2^. 새 메모장 생성 (예: "agile")
    echo 3^. `xnotes/workflow-agile^.md`에서 내용 복사
    echo 4^. 대화에서 `@메모장-이름` 사용
    echo,
    echo ^> **팁:** 메모장 접근 방식은 다음에 이상적입니다:
    echo ^> - 초기 프로젝트 설정
    echo ^> - 스토리 구현
    echo ^> - 집중 개발 세션
    echo ^> - 컨텍스트 오버헤드 감소
    echo,
    echo ## 시작하기
    echo,
    echo 1^. `xnotes/`의 템플릿 검토
    echo 2^. 선호하는 워크플로우 접근 방식 선택
    echo 3^. 자신감을 가지고 AI 사용 시작!
    echo,
    echo 데모 및 튜토리얼은 다음을 방문하세요: [BMad Code 비디오](https://youtube^.com/bmadcode)
) > "%TARGET_DIR%\docs\workflow-rules.md"
echo - workflow-rules.md 생성됨

REM .gitignore 업데이트
echo 📝 .gitignore 업데이트 중...
if exist "%TARGET_DIR%\.gitignore" (
    findstr /L /C:".cursor/rules/_*.mdc" "%TARGET_DIR%\.gitignore" >nul
    if errorlevel 1 (
        (
            echo,
            echo # 개인 사용자 커서 규칙
            echo .cursor/rules/_*.mdc
            echo .cursor/rules/
            echo Cursor/rules/
            echo,
            echo # 문서 및 템플릿
            echo xnotes/
            echo docs/
        ) >> "%TARGET_DIR%\.gitignore"
        echo - .gitignore 업데이트됨
    ) else (
        echo - .gitignore 이미 업데이트됨
    )
) else (
    (
        echo # 개인 사용자 커서 규칙
        echo .cursor/rules/_*.mdc
        echo .cursor/rules/
        echo Cursor/rules/
        echo,
        echo # 문서 및 템플릿
        echo xnotes/
        echo docs/
    ) > "%TARGET_DIR%\.gitignore"
    echo - .gitignore 생성됨
)

REM 메모장 템플릿 설치
echo 📝 메모장 템플릿 설정 중...
if not exist "%TARGET_DIR%\xnotes\" (
    mkdir "%TARGET_DIR%\xnotes"
    echo - xnotes 폴더 생성됨
)

REM 원본 메모장 템플릿 복사 시도
set "XNOTES_SOURCE=%ORIGINAL_FILES_DIR%\..\xnotes"
if exist "%XNOTES_SOURCE%\*.*" (
    xcopy "%XNOTES_SOURCE%\*.*" "%TARGET_DIR%\xnotes\" /E /I /Y >nul
    echo - 원본 템플릿 파일 복사됨
) else (
    echo - 원본 템플릿을 찾을 수 없어 기본 템플릿 생성 중...
    (
        echo # 애자일 워크플로우 메모장
        echo,
        echo 이 메모장은 애자일 워크플로우를 지원하기 위한 템플릿입니다.
        echo,
        echo ## 워크플로우 단계
        echo,
        echo 1. PRD 작성
        echo 2. 아키텍처 설계
        echo 3. 스토리 구현
        echo 4. 테스트 및 검증
        echo 5. 배포
    ) > "%TARGET_DIR%\xnotes\workflow-agile.md"
    echo - 기본 workflow-agile.md 템플릿 생성됨
)

REM Cursor 자동 규칙 추가를 위한 .cursor/settings.json 생성 또는 업데이트
echo ⚙️ Cursor 자동 규칙 설정 중...
if not exist "%TARGET_DIR%\.cursor\" (
    mkdir "%TARGET_DIR%\.cursor"
    echo - .cursor 폴더 생성됨
)

set "SETTINGS_FILE=%TARGET_DIR%\.cursor\settings.json"
set "TEMP_FILE=%TARGET_DIR%\.cursor\settings_temp.json"

if exist "%SETTINGS_FILE%" (
    REM 기존 settings.json 파일이 있는 경우 업데이트
    type "%SETTINGS_FILE%" > "%TEMP_FILE%"
    
    REM rules 경로 추가 확인
    findstr /C:"\"rules\": \[" "%SETTINGS_FILE%" >nul
    if errorlevel 1 (
        REM rules 항목이 없는 경우 추가
        powershell -Command "(Get-Content '%TEMP_FILE%') -replace '(\{)', '$1\n  \"rules\": [\"xnotes/*.md\"],' | Set-Content '%SETTINGS_FILE%'"
        echo - settings.json에 rules 항목 추가됨
    ) else (
        REM rules 항목이 있는 경우 xnotes/*.md 추가 확인
        findstr /C:"xnotes/*.md" "%SETTINGS_FILE%" >nul
        if errorlevel 1 (
            REM xnotes/*.md가 없는 경우 추가
            powershell -Command "(Get-Content '%TEMP_FILE%') -replace '(\"rules\": \[)', '$1\"xnotes/*.md\",' | Set-Content '%SETTINGS_FILE%'"
            echo - settings.json에 xnotes/*.md 항목 추가됨
        ) else (
            echo - settings.json 이미 업데이트됨
        )
    )
) else (
    REM settings.json 파일이 없는 경우 새로 생성
    (
        echo {
        echo   "rules": ["xnotes/*.md"]
        echo }
    ) > "%SETTINGS_FILE%"
    echo - settings.json 생성됨
)

if exist "%TEMP_FILE%" del "%TEMP_FILE%"

REM .cursorignore 업데이트
echo 📝 .cursorignore 업데이트 중...
if exist "%TARGET_DIR%\.cursorignore" (
    findstr /L /C:"xnotes/" "%TARGET_DIR%\.cursorignore" >nul
    if errorlevel 1 (
        (
            echo,
            echo # 프로젝트 노트 및 템플릿
            echo xnotes/
        ) >> "%TARGET_DIR%\.cursorignore"
        echo - .cursorignore 업데이트됨
    ) else (
        echo - .cursorignore 이미 업데이트됨
    )
) else (
    (
        echo # 프로젝트 노트 및 템플릿
        echo xnotes/
    ) > "%TARGET_DIR%\.cursorignore"
    echo - .cursorignore 생성됨
)

REM test.txt 파일 삭제 (존재하는 경우)
if exist "%TARGET_DIR%\test.txt" (
    del "%TARGET_DIR%\test.txt"
)

echo,
echo ✨ 배포 완료!
echo 핵심 규칙: %TARGET_DIR%\.cursor\rules\
echo 메모장 템플릿: %TARGET_DIR%\xnotes\
echo 문서: %TARGET_DIR%\docs\workflow-rules.md
echo .gitignore 및 .cursorignore 업데이트됨
echo xnotes/*.md에서 자동으로 규칙을 추가하도록 Cursor 구성됨

REM 파일 생성 상태 확인
dir "%TARGET_DIR%\.cursor\rules\*.mdc" >nul 2>&1
if errorlevel 1 (
    echo 경고: .cursor\rules 폴더에 .mdc 파일이 없습니다. 확인이 필요합니다.
) else (
    echo .cursor\rules 폴더에 규칙 파일 생성 확인됨.
)

if "%FILES_COPIED%"=="0" (
    echo 원본 파일이 복사되지 않았습니다. 기본 규칙 파일이 생성되었습니다.
) else (
    echo 원본 마크다운 파일 %FILES_COPIED%개가 .mdc로 변환되어 .cursor\rules 폴더에 저장됨
)
echo,
echo 다음 단계:
echo 1^. docs\workflow-rules^.md의 문서 검토
echo 2^. 선호하는 워크플로우 접근 방식 선택
echo 3^. 유연한 워크플로우 옵션을 사용하는 경우 Cursor 메모장 활성화
echo 4^. 새 프로젝트를 시작하려면 xnotes\project-idea-prompt^.md를 템플릿으로 사용하여
echo    AI 에이전트에 보낼 초기 메시지 작성

endlocal
