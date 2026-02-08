"""
VTube Studio 포즈만 테스트하는 스크립트.

- config/pose_mapping.json 을 사용해 감정별 파라미터를 VTS에 보냅니다.
- VTS를 켜고 모델을 로드한 뒤 실행하세요.

사용법 (프로젝트 루트에서):
  # 감정을 3초마다 순서대로 바꿔 가며 테스트 (Ctrl+C 종료)
  python examples/vts_pose_test_example.py

  # 한 감정만 적용 후 2초 뒤 종료
  python examples/vts_pose_test_example.py happy
  python examples/vts_pose_test_example.py sad
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vtuber.vts_client import VTSClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# pose_mapping.json 에 있는 감정 순서 (테스트용)
EMOTIONS_ORDER = ["neutral", "happy", "sad", "angry", "surprised", "excited"]


async def run_cycle(vts: VTSClient, interval: float = 3.0):
    """감정을 순서대로 바꿔 가며 적용. Ctrl+C로 종료."""
    print("감정을 순서대로 적용합니다. (종료: Ctrl+C)\n")
    idx = 0
    while True:
        emotion = EMOTIONS_ORDER[idx % len(EMOTIONS_ORDER)]
        params = vts._emotion_to_parameters(emotion)
        if params:
            print(f"  → {emotion}: {len(params)}개 파라미터 (예: {params[0][0]}={params[0][1]})")
        ok = await vts.set_emotion(emotion)
        if not ok:
            print(f"  실패: {emotion}")
        idx += 1
        await asyncio.sleep(interval)


async def run_once(vts: VTSClient, emotion: str):
    """지정한 감정 한 번만 적용 후 2초 뒤 종료."""
    params = vts._emotion_to_parameters(emotion)
    if not params:
        print(f"pose_mapping.json에 '{emotion}' 감정이 없습니다. 사용 가능: {list(vts.pose_config.get('emotions') or {})}")
        return
    print(f"적용: {emotion} ({len(params)}개 파라미터)")
    for name, val in params[:5]:
        print(f"  {name} = {val}")
    if len(params) > 5:
        print(f"  ... 외 {len(params) - 5}개")
    ok = await vts.set_emotion(emotion)
    print("성공" if ok else "실패")
    await asyncio.sleep(2)


async def main():
    root = Path(__file__).resolve().parent.parent
    pose_config = root / "config" / "pose_mapping.json"
    if not pose_config.exists():
        print("config/pose_mapping.json 이 없습니다. pose_mapping.json.example 을 복사해 설정하세요.")
        return

    vts = VTSClient()
    print("VTube Studio 연결 중... (최초 1회 시 플러그인 허용)")
    if not await vts.connect():
        print("연결 실패. VTS가 실행 중인지, 포트 8001이 열려 있는지 확인하세요.")
        return
    print("연결됨.\n")

    if len(sys.argv) > 1:
        emotion = sys.argv[1].strip().lower()
        await run_once(vts, emotion)
    else:
        try:
            await run_cycle(vts, interval=3.0)
        except KeyboardInterrupt:
            print("\n종료.")

    await vts.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
