"""week06 신청 현황 점검. 실행할 때마다 입력을 새로 읽고 submissions/schedule/신청요약.md를 갱신한다.

실행(week06 폴더에서): python submissions/schedule/check_signup.py
"""

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9), 'Asia/Seoul')
ROOT = Path(__file__).resolve().parents[2]
COND = ROOT / 'practice' / '모임조건.md'
CSV = ROOT / 'practice' / '신청현황.csv'
OUT = Path(__file__).resolve().parent / '신청요약.md'


def field(text, name):
    return re.search(rf'^\|\s*{name}\s*\|\s*(.+?)\s*\|$', text, re.M)[1]


def main():
    now = datetime.now(KST)
    cond = COND.read_text(encoding='utf-8')
    capacity = int(re.search(r'\d+', field(cond, '정원'))[0])
    y, mo, d, h, mi = map(int, re.search(r'(\d{4})년 (\d+)월 (\d+)일 (\d+):(\d+)',
                                          field(cond, '신청 마감')).groups())
    deadline = datetime(y, mo, d, h, mi, tzinfo=KST)

    with CSV.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    applied = [r for r in rows if r['상태'] == '신청']
    cancelled = [r for r in rows if r['상태'] == '취소']
    unknown = [r for r in rows if r['상태'] not in ('신청', '취소')]
    remaining = max(capacity - len(applied), 0)
    over = max(len(applied) - capacity, 0)

    if now < deadline:
        left = deadline - now
        status = f'접수 중 (마감까지 {left.days}일 {left.seconds // 3600}시간 {left.seconds % 3600 // 60}분)'
    else:
        status = '마감됨'

    lines = [
        '# 학과 AI 실습 모임 신청 현황',
        '',
        f"- 실행 시각: {now:%Y-%m-%d %H:%M} (Asia/Seoul)",
        f'- 정원: {capacity}명',
        f'- 현재 신청: {len(applied)}명 ({", ".join(r["이름"] for r in applied)})',
        f'- 취소: {len(cancelled)}명 ({", ".join(r["이름"] for r in cancelled) or "없음"})',
        f'- 남은 자리: {remaining}석' + (f' · 정원 초과 {over}명' if over else ''),
        f'- 신청 마감: {deadline:%Y-%m-%d %H:%M} (Asia/Seoul) · {status}',
    ]
    if unknown:
        lines.append(f'- 확인 필요: 상태값이 신청/취소가 아닌 행 {len(unknown)}건')
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
