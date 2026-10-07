"""수업용 JSON 수치 검사. 입력 보존·보고서 내용·실행 이력은 별도 확인한다."""

import argparse
import json
from pathlib import Path
import re
import sys


def expected_result(data_dir):
    files = sorted(data_dir.glob('warehouse-*.md'))
    if not files:
        raise ValueError('창고 입력 파일이 없습니다.')
    warehouses, items = {}, {}
    for path in files:
        source = path.read_text(encoding='utf-8')
        heading = re.search(r'^# 창고 (\S+) 재고$', source, re.M)
        if not heading or heading[1] in warehouses:
            raise ValueError('창고 제목 누락 또는 중복: ' + path.name)
        rows = re.findall(r'^\|\s*([a-zA-Z0-9_-]+)\s*\|\s*(\d+)\s*\|$', source, re.M)
        if not rows or len({name for name, _ in rows}) != len(rows):
            raise ValueError('품목 행 누락 또는 중복: ' + path.name)
        warehouses[heading[1]] = sum(int(qty) for _, qty in rows)
        for name, qty in rows:
            items[name] = items.get(name, 0) + int(qty)
    return {
        'source_files': [p.name for p in files],
        'warehouse_totals': warehouses,
        'item_totals': items,
        'grand_total': sum(warehouses.values()),
        'low_stock_basis': 'item_total',
        'threshold': 5,
        'low_stock': [{'item': name, 'quantity': qty}
                      for name, qty in sorted(items.items()) if qty < 5],
    }


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON 키 중복: ' + key)
        result[key] = value
    return result


def canonical(value):
    # 키 순서는 무관하지만 1, 1.0, true는 구분한다.
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def check(actual, expected):
    if not isinstance(actual, dict):
        return [('JSON_OBJECT', False)]
    checks = [('FIELDS', set(actual) == set(expected))]
    for key, target in expected.items():
        value = actual.get(key)
        if key in ('source_files', 'low_stock'):
            # 목록 순서는 무관하고 중복·누락·추가 필드는 검출한다.
            ok = isinstance(value, list) and sorted(map(canonical, value)) == sorted(map(canonical, target))
        else:
            ok = canonical(value) == canonical(target)
        checks.append((key, ok))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--data-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'data')
    args = parser.parse_args()
    try:
        expected = expected_result(args.data_dir)
        actual = json.loads(args.result.read_text(encoding='utf-8'),
                            object_pairs_hook=no_duplicate_keys)
        checks = check(actual, expected)
    except (OSError, ValueError) as error:
        print('입력 오류: ' + str(error), file=sys.stderr)
        return 2
    for name, passed in checks:
        print(('통과' if passed else '실패') + ' | ' + name)
    print('범위: JSON 수치·구조. 원본 보존·보고서·실행 이력·최종 저장은 별도 확인.')
    return 0 if all(passed for _, passed in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
