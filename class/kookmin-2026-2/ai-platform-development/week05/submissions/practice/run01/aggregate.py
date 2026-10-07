"""week05 따라하기 1차: 창고별 행 기준 저재고 집계.

입력: practice/data/warehouse-*.md (읽기 전용)
출력: 이 파일과 같은 폴더에 warehouse-A/B/C.json(중간 파일), result.json, report.md
저재고 기준: 창고별 행의 수량 < 5 (low_stock_basis = warehouse_row)

실행(week05 폴더에서): python submissions/practice/run01/aggregate.py
"""

import json
import re
from pathlib import Path

THRESHOLD = 5
OUT = Path(__file__).resolve().parent
DATA = OUT.parents[2] / 'practice' / 'data'


def read_warehouse(path):
    """창고 파일 하나를 읽어 중간 결과를 만든다. 창고끼리 의존하지 않는다."""
    text = path.read_text(encoding='utf-8')
    name = re.search(r'^# 창고 (\S+) 재고$', text, re.M)[1]
    rows = [(item, int(qty)) for item, qty in
            re.findall(r'^\|\s*([a-zA-Z0-9_-]+)\s*\|\s*(\d+)\s*\|$', text, re.M)]
    return {
        'source_file': path.name,
        'warehouse': name,
        'total': sum(q for _, q in rows),
        'items': dict(rows),
        'low_stock': [{'item': i, 'warehouse': name, 'quantity': q}
                      for i, q in rows if q < THRESHOLD],
    }


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    # 1단계: 창고 A·B·C 독립 집계 -> 중간 파일
    parts = []
    for path in sorted(DATA.glob('warehouse-*.md')):
        part = read_warehouse(path)
        write_json(OUT / f"warehouse-{part['warehouse']}.json", part)
        parts.append(part)

    # 2단계: 통합
    item_totals = {}
    for part in parts:
        for item, qty in part['items'].items():
            item_totals[item] = item_totals.get(item, 0) + qty
    result = {
        'source_files': [p['source_file'] for p in parts],
        'warehouse_totals': {p['warehouse']: p['total'] for p in parts},
        'item_totals': item_totals,
        'grand_total': sum(p['total'] for p in parts),
        'low_stock_basis': 'warehouse_row',
        'threshold': THRESHOLD,
        'low_stock': [row for p in parts for row in p['low_stock']],
    }
    write_json(OUT / 'result.json', result)

    lines = ['# 재고 요약 보고서 (1차 · 창고별 행 기준)', '',
             f"입력: {', '.join(result['source_files'])}", '',
             '## 창고별 합계', '', '| 창고 | 합계 |', '|---|---:|']
    lines += [f'| {w} | {t} |' for w, t in result['warehouse_totals'].items()]
    lines += ['', '## 품목별 총수량', '', '| 품목 | 총수량 |', '|---|---:|']
    lines += [f'| {i} | {q} |' for i, q in item_totals.items()]
    lines += ['', f"전체 수량: {result['grand_total']}", '',
              '## 저재고', '',
              f'기준: 창고별 행의 수량이 {THRESHOLD} 미만 (low_stock_basis = warehouse_row)', '',
              '| 창고 | 품목 | 수량 |', '|---|---|---:|']
    lines += [f"| {r['warehouse']} | {r['item']} | {r['quantity']} |" for r in result['low_stock']]
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
