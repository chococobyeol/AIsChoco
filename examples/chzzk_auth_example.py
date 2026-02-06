"""
치지직 Access Token 발급 예제

사용 방법:
1. 프로젝트 루트에 .env 파일 생성 후 CHZZK_CLIENT_ID, CHZZK_CLIENT_SECRET, CHZZK_REDIRECT_URI 입력
2. 이 스크립트 실행하여 인증 URL 생성
3. 브라우저에서 인증 URL 열기
4. 로그인 후 리디렉션 URL에서 code와 state 추출
5. 터미널에 code와 state 입력하여 토큰 발급
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 넣어서 'import src' 가능하게 함
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import os

from dotenv import load_dotenv

from src.utils.chzzk_auth import ChzzkAuth

# 프로젝트 루트의 .env 로드 (examples/에서 실행해도 동작)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def main():
    # .env에서 읽기 (비밀 정보는 코드에 넣지 않음 → GitHub 업로드 안전)
    CLIENT_ID = os.getenv("CHZZK_CLIENT_ID")
    CLIENT_SECRET = os.getenv("CHZZK_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("CHZZK_REDIRECT_URI", "http://localhost:8080/callback")

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ .env 파일에 CHZZK_CLIENT_ID, CHZZK_CLIENT_SECRET을 설정해주세요.")
        return

    # 인증 클래스 생성
    auth = ChzzkAuth(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    
    # 1단계: 인증 URL 생성
    auth_url = auth.get_authorization_url()
    print("=" * 60)
    print("1. 아래 URL을 브라우저에서 열어주세요:")
    print("=" * 60)
    print(auth_url)
    print("=" * 60)
    print("\n2. 로그인 후 리디렉션 URL에서 code와 state를 복사하세요.")
    print("   예: http://localhost:8080/callback?code=XXX&state=YYY\n")
    
    # 2단계: 사용자 입력 받기
    code = input("인증 코드 (code): ").strip()
    state = input("상태 값 (state): ").strip()
    
    # 3단계: Access Token 발급
    try:
        token = await auth.exchange_code_for_token(code, state)
        print("\n✅ Access Token 발급 성공!")
        print(f"   만료 시각: {token.expires_at}")
        print("\n--- .env에 아래 한 줄 추가하세요 (채팅 예제용) ---")
        print(f"CHZZK_ACCESS_TOKEN={token.access_token}")
        print("--- (Refresh Token은 갱신 시 사용, 필요 시 따로 보관) ---")
        print(f"   Refresh Token: {token.refresh_token}")
        print("------------------------------------------------")
        
        # 4단계: 토큰 사용 예제 (세션 생성 API 호출)
        print("\n4. 세션 생성 API 호출 테스트...")
        valid_token = await auth.get_valid_token()
        print(f"   유효한 토큰: {valid_token[:20]}...")
        
        # 만료 시 자동 갱신 테스트 (선택사항)
        # print("\n5. 토큰 갱신 테스트...")
        # refreshed_token = await auth.refresh_token()
        # print(f"   갱신된 토큰: {refreshed_token.access_token[:20]}...")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
