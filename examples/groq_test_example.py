"""
Groq API 키 동작 확인 예제

.env에 GROQ_API_KEY 설정 후 실행.
실행: python examples/groq_test_example.py  (프로젝트 루트에서)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def main():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "여기에-groq-api-key-입력":
        print("오류: .env에 GROQ_API_KEY를 설정해 주세요.")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("오류: openai 패키지가 필요합니다. pip install openai")
        sys.exit(1)

    print("Groq API 호출 중...")
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "한 줄로 짧게 인사해줘."}],
        max_tokens=64,
    )
    choices = getattr(response, "choices", None) or []
    if not choices or getattr(choices[0], "message", None) is None:
        print("응답이 비어 있습니다.")
        sys.exit(1)
    reply = (choices[0].message.content or "").strip()
    print("응답:", reply)
    print("Groq API 키 정상 동작합니다.")


if __name__ == "__main__":
    main()
