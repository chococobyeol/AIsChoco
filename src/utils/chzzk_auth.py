"""
치지직 API 인증 유틸리티
Access Token 발급 및 갱신을 담당합니다.

참고: https://chzzk.gitbook.io/chzzk/chzzk-api/authorization
"""

import secrets
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChzzkToken:
    """치지직 Access Token 정보"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 초 단위 (기본 1일)
    expires_at: Optional[datetime] = None  # 만료 시각
    
    def __post_init__(self):
        """만료 시각 자동 계산"""
        if self.expires_at is None:
            self.expires_at = datetime.now() + timedelta(seconds=self.expires_in)
    
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인 (5분 여유)"""
        if self.expires_at is None:
            return False
        return datetime.now() >= (self.expires_at - timedelta(minutes=5))


class ChzzkAuth:
    """치지직 API 인증 클래스"""
    
    # 인증 코드 요청: chzzk.naver.com (문서: account-interlock)
    AUTH_BASE_URL = "https://chzzk.naver.com"
    # 토큰/세션 등 Open API: openapi.chzzk.naver.com (참고사항 문서, 하이픈 없음)
    API_BASE_URL = "https://openapi.chzzk.naver.com"
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Args:
            client_id: 치지직 애플리케이션 Client ID
            client_secret: 치지직 애플리케이션 Client Secret
            redirect_uri: 등록한 리디렉션 URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.current_token: Optional[ChzzkToken] = None
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        인증 코드 요청 URL 생성
        
        Args:
            state: CSRF 방지를 위한 랜덤 문자열 (없으면 자동 생성)
        
        Returns:
            인증 코드 요청 URL
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        
        params = {
            "clientId": self.client_id,
            "redirectUri": self.redirect_uri,
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTH_BASE_URL}/account-interlock?{query_string}"
    
    async def exchange_code_for_token(
        self,
        code: str,
        state: str
    ) -> ChzzkToken:
        """
        인증 코드를 Access Token으로 교환
        
        Args:
            code: 인증 코드 (리디렉션 URL에서 받은 code 파라미터)
            state: 상태 값 (리디렉션 URL에서 받은 state 파라미터)
        
        Returns:
            ChzzkToken 객체
        
        Raises:
            httpx.HTTPStatusError: API 호출 실패 시
        """
        url = f"{self.API_BASE_URL}/auth/v1/token"
        
        data = {
            "grantType": "authorization_code",
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "code": code,
            "state": state
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            # 공통 응답: {"code": 200, "message": null, "content": { accessToken, ... }}
            body = result.get("content") if result.get("content") is not None else result
            access_token = body.get("accessToken") or body.get("access_token")
            refresh_token = body.get("refreshToken") or body.get("refresh_token")
            if not access_token or not refresh_token:
                logger.error(f"토큰 API 응답에 accessToken/refreshToken 없음: {result}")
                raise ValueError(
                    f"토큰 API가 예상과 다른 응답을 반환했습니다. 응답: {result}"
                )
            token = ChzzkToken(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=body.get("tokenType") or body.get("token_type", "Bearer"),
                expires_in=int(body.get("expiresIn") or body.get("expires_in", 86400))
            )
            
            self.current_token = token
            logger.info(f"Access Token 발급 성공 (만료: {token.expires_at})")
            return token
    
    async def refresh_token(self) -> ChzzkToken:
        """
        Refresh Token을 사용하여 Access Token 갱신
        
        Returns:
            새로운 ChzzkToken 객체
        
        Raises:
            ValueError: Refresh Token이 없는 경우
            httpx.HTTPStatusError: API 호출 실패 시
        """
        if not self.current_token or not self.current_token.refresh_token:
            raise ValueError("Refresh Token이 없습니다. 먼저 인증 코드로 토큰을 발급받아야 합니다.")
        
        url = f"{self.API_BASE_URL}/auth/v1/token"
        
        data = {
            "grantType": "refresh_token",
            "refreshToken": self.current_token.refresh_token,
            "clientId": self.client_id,
            "clientSecret": self.client_secret
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            body = result.get("content") if result.get("content") is not None else result
            token = ChzzkToken(
                access_token=body.get("accessToken") or body.get("access_token"),
                refresh_token=body.get("refreshToken") or body.get("refresh_token"),
                token_type=body.get("tokenType") or body.get("token_type", "Bearer"),
                expires_in=int(body.get("expiresIn") or body.get("expires_in", 86400))
            )
            self.current_token = token
            logger.info(f"Access Token 갱신 성공 (만료: {token.expires_at})")
            return token
    
    async def get_valid_token(self) -> str:
        """
        유효한 Access Token 반환 (만료 시 자동 갱신)
        
        Returns:
            Access Token 문자열
        """
        if not self.current_token:
            raise ValueError("토큰이 없습니다. 먼저 인증 코드로 토큰을 발급받아야 합니다.")
        
        if self.current_token.is_expired():
            logger.info("Access Token 만료됨. Refresh Token으로 갱신 중...")
            await self.refresh_token()
        
        return self.current_token.access_token
    
    async def revoke_token(self, token_type_hint: str = "access_token") -> bool:
        """
        Access Token 또는 Refresh Token 삭제
        
        Args:
            token_type_hint: "access_token" 또는 "refresh_token"
        
        Returns:
            성공 여부
        """
        if not self.current_token:
            return False
        
        url = f"{self.API_BASE_URL}/auth/v1/token/revoke"
        
        token = (
            self.current_token.access_token
            if token_type_hint == "access_token"
            else self.current_token.refresh_token
        )
        
        data = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "token": token,
            "tokenTypeHint": token_type_hint
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                logger.info(f"Token 삭제 성공: {token_type_hint}")
                return True
        except Exception as e:
            logger.error(f"Token 삭제 실패: {e}")
            return False
