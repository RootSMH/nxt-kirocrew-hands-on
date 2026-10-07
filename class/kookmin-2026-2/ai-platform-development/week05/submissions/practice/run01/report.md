# 재고 요약 보고서 (1차 · 창고별 행 기준)

입력: warehouse-a.md, warehouse-b.md, warehouse-c.md

## 창고별 합계

| 창고 | 합계 |
|---|---:|
| A | 22 |
| B | 16 |
| C | 16 |

## 품목별 총수량

| 품목 | 총수량 |
|---|---:|
| mug | 17 |
| bottle | 12 |
| sensor | 11 |
| hub | 13 |
| cable | 1 |

전체 수량: 54

## 저재고

기준: 창고별 행의 수량이 5 미만 (low_stock_basis = warehouse_row)

| 창고 | 품목 | 수량 |
|---|---|---:|
| A | bottle | 3 |
| B | hub | 2 |
| C | sensor | 4 |
| C | cable | 1 |
