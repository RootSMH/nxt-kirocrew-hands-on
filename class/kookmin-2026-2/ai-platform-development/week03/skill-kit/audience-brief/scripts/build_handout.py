#!/usr/bin/env python3
"""검토한 청중별 원고를 고정 HTML 양식에 조립한다. Python 3.10+, 표준 라이브러리만 사용."""

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


class InputError(ValueError):
    """원고 또는 템플릿이 입력 계약과 맞지 않는다."""


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{label}: 비어 있지 않은 문자열이 필요합니다.")
    return value  # 사실·원고를 자동 교정하거나 요약하지 않는다.


def items(value, label):
    if not isinstance(value, list) or not value:
        raise InputError(f"{label}: 항목이 한 개 이상 있는 목록이 필요합니다.")
    if not all(isinstance(item, dict) for item in value):
        raise InputError(f"{label}: 각 항목은 JSON 객체여야 합니다.")
    return value


def validate(document):
    if not isinstance(document, dict):
        raise InputError("입력은 JSON 객체여야 합니다.")
    text(document.get("title"), "title")
    text(document.get("audience"), "audience")
    source_numbers = {}
    for index, source in enumerate(items(document.get("sources"), "sources"), 1):
        source_id = text(source.get("id"), "sources.id")
        if source_id in source_numbers:
            raise InputError(f"출처 ID가 중복되었습니다: {source_id}")
        text(source.get("title"), f"출처 {source_id} title")
        url = text(source.get("url"), f"출처 {source_id} url")
        try:
            parsed = urlsplit(url)
            valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:
            valid_url = False
        if not valid_url or any(character.isspace() or ord(character) < 32 for character in url):
            raise InputError(f"출처 {source_id}: 유효한 http/https URL이 필요합니다.")
        source_numbers[source_id] = index

    fact_ids = set()
    for fact in items(document.get("facts"), "facts"):
        fact_id = text(fact.get("id"), "facts.id")
        if fact_id in fact_ids:
            raise InputError(f"사실 ID가 중복되었습니다: {fact_id}")
        fact_ids.add(fact_id)
        text(fact.get("text"), f"사실 {fact_id} text")

    for index, section in enumerate(items(document.get("sections"), "sections"), 1):
        text(section.get("heading"), f"sections {index} heading")
        text(section.get("body"), f"sections {index} body")
        references = section.get("source_ids", [])
        if not isinstance(references, list) or not all(isinstance(ref, str) for ref in references):
            raise InputError(f"sections {index} source_ids는 출처 ID 문자열 목록이어야 합니다.")
        if len(set(references)) != len(references):
            raise InputError(f"sections {index}: 같은 출처 ID를 중복 지정했습니다.")
        missing = [ref for ref in references if ref not in source_numbers]
        if missing:
            raise InputError(f"sections {index}: 등록되지 않은 출처 ID: {', '.join(missing)}")
    return source_numbers


def validate_evidence(document, evidence):
    """검토한 공통근거와 값·목록 순서를 비교한다. 문장의 진실성은 판정하지 않는다."""
    if not isinstance(evidence, dict):
        raise InputError("공통근거 파일은 facts와 sources를 담은 JSON 객체여야 합니다.")
    for key in ("facts", "sources"):
        items(evidence.get(key), f"공통근거 {key}")
        if document[key] != evidence[key]:
            raise InputError(
                f"{key}가 공통근거 파일과 다릅니다. 값과 항목 순서를 같게 맞춘 뒤 다시 실행하세요."
            )


def build(document, template, evidence=None):
    """내용은 escape하고, 구조와 출처 번호만 코드가 만든다."""
    numbers = validate(document)
    if evidence is not None:
        validate_evidence(document, evidence)
    escape = lambda value: html.escape(str(value), quote=True)
    sections = []
    for section in document["sections"]:
        citations = " ".join(
            f'<a href="#source-{numbers[ref]}" aria-label="출처 {numbers[ref]}">[{numbers[ref]}]</a>'
            for ref in section.get("source_ids", [])
        )
        sections.append(
            f'<section class="explanation"><h2>{escape(section["heading"])}</h2>'
            f'<p class="body-text">{escape(section["body"])}</p>'
            + (f'<p class="citations">관련 출처 {citations}</p>' if citations else "")
            + "</section>"
        )
    # 두 청중에게 같은 facts 배열을 주면 이 블록은 정확히 같아진다.
    facts = "<ul>" + "".join(
        f'<li><span class="fact-id">{escape(fact["id"])}</span> '
        f'<span class="fact-text">{escape(fact["text"])}</span></li>'
        for fact in document["facts"]
    ) + "</ul>"
    sources = "<ol>" + "".join(
        f'<li id="source-{numbers[source["id"]]}"><a href="{escape(source["url"])}" '
        f'rel="noopener noreferrer">{escape(source["title"])}</a>'
        f'<span class="source-url">{escape(source["url"])}</span></li>'
        for source in document["sources"]
    ) + "</ol>"
    replacements = {
        "TITLE": escape(document["title"]),
        "AUDIENCE": escape(document["audience"]),
        "SECTIONS": "\n".join(sections),
        "FACTS": facts,
        "SOURCES": sources,
    }
    placeholder = re.compile(r"\{\{([^{}]*)\}\}")
    found = {match.group(1).strip() for match in placeholder.finditer(template)}
    unknown, missing = found - replacements.keys(), replacements.keys() - found
    residue = placeholder.sub("", template)
    if unknown or missing or "{{" in residue or "}}" in residue:
        raise InputError(
            "템플릿 자리표시자가 맞지 않습니다. "
            f"미등록: {', '.join(sorted(unknown)) or '없음'}, "
            f"누락: {', '.join(sorted(missing)) or '없음'}. "
            "TITLE, AUDIENCE, SECTIONS, FACTS, SOURCES를 {{이름}} 형태로 사용하세요."
        )
    # 템플릿만 한 번 치환한다. 원고의 {{문자}}를 템플릿 명령으로 해석하지 않는다.
    return placeholder.sub(lambda match: replacements[match.group(1).strip()], template)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"JSON 키가 중복되었습니다: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise InputError(f"JSON에 허용되지 않는 숫자입니다: {value}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique_object, parse_constant=reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="title, audience, sections, facts, sources를 담은 JSON")
    parser.add_argument("--template", required=True, type=Path, help="공통 handout.html 양식")
    parser.add_argument("--evidence", type=Path, help="facts/sources 값과 순서를 대조할 공통근거 JSON. 이 수업에서 사용 권장")
    parser.add_argument("--output", required=True, type=Path, help="완성 HTML 저장 경로. 원고·템플릿과 달라야 함")
    args = parser.parse_args(argv)
    try:
        input_paths = [args.input, args.template, Path(__file__)]
        if args.evidence:
            input_paths.append(args.evidence)
        inputs = {path.resolve() for path in input_paths}
        if args.output.resolve() in inputs:
            raise InputError("출력 경로가 원고·공통근거·템플릿·스크립트와 같습니다. 다른 경로를 지정하세요.")
        if args.output.exists() and any(path.exists() and args.output.samefile(path) for path in inputs):
            raise InputError("출력 경로가 원고·공통근거·템플릿·스크립트와 같은 파일을 가리킵니다.")
        document = read_json(args.input)
        evidence = read_json(args.evidence) if args.evidence else None
        # --evidence를 줬는데 JSON null인 경우도 생략한 것으로 취급하지 않는다.
        if args.evidence and not isinstance(evidence, dict):
            raise InputError("공통근거 파일은 facts와 sources를 담은 JSON 객체여야 합니다.")
        result = build(document, args.template.read_text(encoding="utf-8"), evidence)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
        print(f"저장: {args.output.resolve()}")
    except (InputError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"오류: {exc}\n")


if __name__ == "__main__":
    main()
