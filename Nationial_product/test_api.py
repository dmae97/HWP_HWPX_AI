#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API 연결 테스트 스크립트

이 스크립트는 Gemini API와 Perplexity API에 연결할 수 있는지 테스트합니다.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv
import traceback

# 환경 변수 로드
load_dotenv()

def test_gemini_api():
    """
    Google Gemini API 연결을 테스트합니다.
    """
    try:
        # API 키 확인
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ Google API 키가 설정되지 않았습니다. .env 파일에 GOOGLE_API_KEY를 설정하세요.")
            return False
        
        # Gemini API 임포트 테스트
        import google.generativeai as genai
        
        # API 구성
        genai.configure(api_key=api_key)
        
        # 모델 생성
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={
                "temperature": 0.2,
                "top_p": 0.95,
                "max_output_tokens": 100,
            }
        )
        
        # 간단한 쿼리 실행
        response = model.generate_content("안녕하세요!")
        
        print(f"✅ Gemini API 테스트 성공: {response.text}")
        return True
    
    except Exception as e:
        print(f"❌ Gemini API 테스트 실패: {str(e)}")
        print("상세 오류:")
        traceback.print_exc()
        return False

def test_perplexity_api():
    """
    Perplexity API 연결을 테스트합니다.
    """
    try:
        # API 키 확인
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            print("❌ Perplexity API 키가 설정되지 않았습니다. .env 파일에 PERPLEXITY_API_KEY를 설정하세요.")
            return False
        
        # API 요청
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "mistral-7b-instruct",  # 가장 기본적인 모델로 시도
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "안녕하세요, 간단한 테스트입니다."}
            ],
            "max_tokens": 100,
            "temperature": 0.2
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ Perplexity API 테스트 성공: {content[:50]}...")
            return True
        else:
            print(f"❌ Perplexity API 테스트 실패 - 상태 코드: {response.status_code}")
            print(f"응답: {response.text}")
            
            # 사용 가능한 모델 목록 출력 시도
            print("\n사용 가능한 모델 목록을 확인하려면 다음 URL을 참조하세요:")
            print("https://docs.perplexity.ai/guides/model-cards")
            return False
    
    except Exception as e:
        print(f"❌ Perplexity API 테스트 실패: {str(e)}")
        print("상세 오류:")
        traceback.print_exc()
        return False

def test_hwp_handler():
    """
    HwpHandler 기능을 테스트합니다.
    """
    try:
        from hwp_utils import HwpHandler
        print("✅ HwpHandler 모듈 임포트 성공")
        return True
    except Exception as e:
        print(f"❌ HwpHandler 모듈 임포트 실패: {str(e)}")
        print("상세 오류:")
        traceback.print_exc()
        return False

def main():
    """
    메인 함수
    """
    print("===== API 연결 테스트 시작 =====")
    
    # .env 파일 확인
    if not os.path.exists(".env"):
        print("⚠️ .env 파일이 존재하지 않습니다. .env.example 파일을 복사하여 .env 파일을 생성하세요.")
    
    # Google Gemini API 테스트
    print("\n----- Google Gemini API 테스트 -----")
    gemini_result = test_gemini_api()
    
    # Perplexity API 테스트
    print("\n----- Perplexity API 테스트 -----")
    perplexity_result = test_perplexity_api()
    
    # HwpHandler 테스트
    print("\n----- HwpHandler 테스트 -----")
    hwp_result = test_hwp_handler()
    
    # 결과 요약
    print("\n===== 테스트 결과 요약 =====")
    print(f"Google Gemini API: {'✅ 성공' if gemini_result else '❌ 실패'}")
    print(f"Perplexity API: {'✅ 성공' if perplexity_result else '❌ 실패'}")
    print(f"HwpHandler: {'✅ 성공' if hwp_result else '❌ 실패'}")
    
    if gemini_result and perplexity_result and hwp_result:
        print("\n🎉 모든 테스트가 성공했습니다!")
        print("애플리케이션을 실행하려면 'streamlit run app.py' 명령어를 실행하세요.")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다. 상세 오류 메시지를 확인하세요.")
        print("문제를 해결한 후 다시 테스트해주세요.")

if __name__ == "__main__":
    main() 