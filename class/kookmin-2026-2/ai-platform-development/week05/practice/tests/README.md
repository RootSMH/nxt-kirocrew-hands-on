# 경계값 검사

boundary-data는 기본 창고 원본과 독립된 테스트 입력입니다. 품목별 합계가 4·5·6인 경우를 비교합니다. 5 미만이라는 조건에서 정확히 5인 품목이 들어가는지 확인하세요.

별도의 결과 JSON을 만든 뒤 week05 폴더에서 다음과 같이 검사합니다.

```sh
python3 practice/tests/check_result.py submissions/practice/boundary/result.json --data-dir practice/tests/boundary-data
```

이때 source_files와 warehouse_totals는 경계값 입력에 맞게 작성합니다. 기본 창고 합계와 섞지 않습니다.
