(() => {
  'use strict';
  const root = document.getElementById('mission-submission');
  if (!root) return;
  const fields = [...root.querySelectorAll('[data-mission-field]')];
  const required = fields.filter(field => field.dataset.requiredLabel);
  const storageKey = 'kookmin-week06-mission-draft';
  const saveStatus = document.getElementById('mission-save-status');
  const record = document.getElementById('mission-record');
  const completeness = document.getElementById('mission-completeness');
  const downloadStatus = document.getElementById('mission-download-status');
  const value = id => document.getElementById(id).value;
  const content = id => value(id).trim() ? value(id) : '[미작성]';
  const missing = () => required.filter(field => !field.value.trim());

  function codeBlock(text) {
    const runs = text.match(/`+/g) || [];
    const fence = '`'.repeat(Math.max(3, ...runs.map(run => run.length + 1)));
    return `${fence}text\n${text}\n${fence}`;
  }

  function buildRecord() {
    const parts = [
      '# 6주차 미션 제출 기록',
      '## 1. 스케줄 등록 내용',
      `- 작업명: ${content('mission-name')}\n- 실행 주기·시각·시간대: ${content('mission-cycle')}`,
      '### 실제 등록한 프롬프트',
      codeBlock(content('mission-prompt')),
      '설정 화면: `스케줄설정.png`',
      '## 2. 첫 실행과 재실행',
      '### 변경한 입력 파일과 내용',
      content('mission-change'),
      '### 결과에서 달라진 부분',
      content('mission-difference'),
      '결과 파일: `첫결과.md`, `재실행결과.md`',
      '## 3. DAG의 HITL 설정',
      '### 승인 필요로 설정한 단계 이름',
      content('mission-hitl-stage'),
      '### 그 단계에서 실행될 행동',
      content('mission-hitl-action'),
      '### 해당 지점에 사람의 승인이 필요한 이유',
      content('mission-hitl-reason'),
      '설정 화면: `DAG_HITL.png`'
    ];
    if (value('mission-dag-prompt').trim()) {
      parts.push('### DAG 생성에 사용한 요청', codeBlock(value('mission-dag-prompt')));
    }
    parts.push('## 제출 확인', [
      '- [ ] 실제 등록한 작업명·실행 주기·프롬프트가 기록과 일치한다.',
      '- [ ] 스케줄설정.png에서 내 작업명과 실행 주기를 읽을 수 있다.',
      '- [ ] 첫결과.md와 재실행결과.md를 각각 열어 확인했다.',
      '- [ ] 변경한 입력과 결과의 차이를 적었다.',
      '- [ ] DAG_HITL.png의 승인 단계와 기록한 이유가 일치한다.',
      '- [ ] 스케줄을 일시 중지했다.',
      '- [ ] 본인 GitHub 저장소의 main에 커밋·푸시하고 다섯 파일을 열어 확인했다.'
    ].join('\n'));
    return parts.join('\n\n') + '\n';
  }

  function updateFieldDisplay(field) {
    if (field.tagName !== 'TEXTAREA') return;
    const printCopy = field.nextElementSibling;
    if (printCopy && printCopy.classList.contains('print-copy')) {
      printCopy.textContent = field.value;
    }
    if (field.getClientRects().length) {
      field.style.height = 'auto';
      field.style.height = (field.scrollHeight + 2) + 'px';
    }
  }

  function updateRecord() {
    record.value = buildRecord();
    updateFieldDisplay(record);
    const unfilled = missing();
    completeness.textContent = unfilled.length
      ? `아직 작성할 항목 ${unfilled.length}개: ${unfilled.map(field => field.dataset.requiredLabel).join(' · ')}`
      : '기록 항목을 모두 작성했습니다. 실제 앱 설정과 일치하는지 확인하고, 결과 파일 두 개와 스크린샷 두 장도 준비하세요.';
  }

  try {
    const savedText = localStorage.getItem(storageKey);
    if (savedText) {
      const saved = JSON.parse(savedText);
      if (!saved || saved.schema !== 1 || !saved.fields || typeof saved.fields !== 'object') {
        throw new Error('Invalid draft');
      }
      fields.forEach(field => {
        if (typeof saved.fields[field.id] === 'string') field.value = saved.fields[field.id];
      });
      saveStatus.textContent = '이 브라우저에 임시 저장된 작성 내용을 불러왔습니다.';
    }
  } catch (_) {
    saveStatus.textContent = '브라우저 임시 저장을 사용할 수 없거나 기록을 불러오지 못했습니다. 작성 내용은 다운로드 또는 복사로 보관하세요.';
  }

  fields.forEach(field => {
    updateFieldDisplay(field);
    field.addEventListener('input', () => {
      updateFieldDisplay(field);
      updateRecord();
      downloadStatus.textContent = '';
      try {
        const data = Object.fromEntries(fields.map(item => [item.id, item.value]));
        localStorage.setItem(storageKey, JSON.stringify({schema: 1, fields: data}));
        saveStatus.textContent = '작성 내용을 이 브라우저에 임시 저장했습니다. 제출 파일은 마지막에 다운로드하세요.';
      } catch (_) {
        saveStatus.textContent = '브라우저 임시 저장이 되지 않습니다. 페이지를 닫기 전에 다운로드 또는 복사로 보관하세요.';
      }
    });
  });

  root.querySelectorAll('details').forEach(details => {
    details.addEventListener('toggle', () => {
      if (details.open) details.querySelectorAll('textarea').forEach(updateFieldDisplay);
    });
  });

  document.getElementById('mission-download').addEventListener('click', () => {
    updateRecord();
    const blob = new Blob([record.value], {type: 'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '제출기록.md';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    downloadStatus.textContent = missing().length
      ? '현재 작성분의 다운로드를 요청했습니다. [미작성] 항목을 채운 뒤 최종 파일을 다시 저장하세요.'
      : '다운로드를 요청했습니다. 내려받은 제출기록.md를 week06/submissions/mission/으로 옮겨 내용을 확인하세요.';
  });
  updateRecord();
})();
