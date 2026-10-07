# 검증용 결과 예제

이 폴더는 강사의 안내 후 여세요. 실제 에이전트 실행 결과가 아닌, 검증 수업을 위해 만든 정상·오류 예제입니다. 어떤 검사가 오류를 찾는지 확인하는 데 사용합니다.

- normal.json: 정상 결과.
- error-a.json ~ error-d.json: 각각 의도적 오류가 있는 결과.

week05 폴더에서 예제 하나씩 검사합니다.

```sh
python3 practice/tests/check_result.py practice/cases/normal.json
python3 practice/tests/check_result.py practice/cases/error-a.json
```

오류 파일은 종료 코드 1이 나오는 것이 예상 동작입니다. JSON 검사 외에 보고서 내용과 저장 위치를 어떻게 확인할지도 설명하세요.
