#!/usr/bin/env python3
"""
블로그 아카이브 깊이 추출 — 배치 처리 + Haiku 버전 (토큰 절약).

기존 deep_archive_extractor.py의 효율 개선:
- Sonnet → Haiku 4.5 (비용 1/12)
- 1개씩 호출 → 5개씩 배치 (시스템 프롬프트 비용 5배 절감)
- 전체: 약 60배 토큰 절감

사용법:
    python3 deep_archive_extractor_batch.py <폴더> [출력JSON] [--parallel N] [--batch N]
"""

import sys
import os
import re
import json
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


BATCH_PROMPT_HEADER = """다음 블로그 글들의 사고 구조를 각각 추출해서 JSON 배열로 출력해라.
설명·주석·코드블록 금지. JSON 배열 하나만 출력.

각 글마다 다음 스키마 객체를 만든다:
{"id":<글번호>,"핵심_메시지":"한 줄","멘탈모델":["1-4개"],"재정의_문장":"A가 아니라 B다 형식 원문 또는 빈 문자열","독특한_표현":["0-3개"],"키워드":["3-5개"],"주제분류":"투자|부동산|거시|기술AI|지정학|메타인지|역사|심리|철학|개인|기타","통찰_한줄":"원문 인용","감성":"분석|성찰|비판|낙관|비관|중립"}

응답 형식 (JSON 배열):
[{"id":1,...},{"id":2,...},...]

==================
"""


def extract_content(filepath: Path) -> dict:
    """마크다운 파일에서 제목·본문 추출"""
    text = filepath.read_text(encoding='utf-8', errors='ignore')

    if text.startswith('---'):
        end = text.find('---', 3)
        if end != -1:
            text = text[end + 3:].lstrip()

    title = ''
    title_m = re.search(r'^#\s+(.+)', text, flags=re.MULTILINE)
    if title_m:
        title = title_m.group(1).strip()
    else:
        title = filepath.stem

    body = re.sub(r'^#\s+.+\n', '', text, count=1)
    body = re.sub(r'\n?---\n※.*$', '', body, flags=re.DOTALL).strip()

    return {'title': title, 'body': body, 'filename': filepath.name}


def extract_log_no(filename: str) -> str:
    """파일명에서 logNo 추출 (구/신 포맷 모두)."""
    m = re.search(r'(?:\d{4}-\d{2}-\d{2}_)?(\d+)_', filename)
    return m.group(1) if m else filename


def call_claude(prompt: str, model: str = "haiku", timeout: int = 240) -> tuple:
    """Claude CLI print 모드 호출. (stdout, err_msg) 반환. err_msg 있으면 호출 실패."""
    try:
        result = subprocess.run(
            ["claude", "--print", "--model", model, "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return "", f"returncode={result.returncode} stderr={result.stderr[:200]}"
        return result.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except Exception as e:
        return "", f"exception={e}"


def parse_json_array(response: str) -> list:
    """JSON 배열 추출"""
    if not response:
        return None

    response = re.sub(r'^```(?:json)?\s*', '', response.strip())
    response = re.sub(r'\s*```$', '', response.strip())

    try:
        result = json.loads(response)
        return result if isinstance(result, list) else None
    except json.JSONDecodeError:
        # [ ... ] 패턴 찾기
        m = re.search(r'\[[\s\S]*\]', response)
        if m:
            try:
                result = json.loads(m.group(0))
                return result if isinstance(result, list) else None
            except json.JSONDecodeError:
                return None
        return None


def process_batch(batch: list, max_retries: int = 2, model: str = "haiku") -> dict:
    """배치 처리 — 여러 글을 한 번에 추출"""
    # 배치 프롬프트 구성
    sections = []
    file_data = {}
    for idx, filepath in enumerate(batch, 1):
        try:
            data = extract_content(filepath)
            log_no = extract_log_no(filepath.name)
            body = data['body'][:4000]  # 배치라서 글당 본문 짧게
            sections.append(f"[글 {idx}]\n제목: {data['title']}\n본문:\n{body}\n")
            file_data[idx] = {
                'log_no': log_no,
                'title': data['title'],
                'filename': filepath.name,
            }
        except Exception:
            continue

    if not sections:
        return {}

    prompt = BATCH_PROMPT_HEADER + "\n\n".join(sections) + "\n\n다시 강조: JSON 배열만 출력. 설명 금지."

    # 재시도 포함 호출
    parsed = None
    last_err = ""
    response = ""
    for attempt in range(max_retries + 1):
        response, last_err = call_claude(prompt, model=model)
        if last_err:
            # CLI 호출 자체 실패 (토큰 만료 포함) — 즉시 리턴
            print(f"  call_claude 실패: {last_err}", file=sys.stderr)
            return {"__call_error__": last_err}
        parsed = parse_json_array(response)
        if parsed:
            break
        time.sleep(2)

    if not parsed:
        # 응답은 왔지만 파싱 실패 — 디버그 저장
        debug_dir = Path("/tmp/brain_fail")
        debug_dir.mkdir(exist_ok=True)
        first_log = file_data.get(1, {}).get('log_no', 'unknown')
        (debug_dir / f"batch_{first_log}.txt").write_text(
            f"=== PROMPT LEN ===\n{len(prompt)}\n=== RESPONSE ===\n{response[:3000] if response else '(empty)'}\n",
            encoding='utf-8'
        )
        return {}

    # 결과 매칭
    results = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        item_id = item.get('id')
        if item_id is None or item_id not in file_data:
            continue
        meta = file_data[item_id]
        item['log_no'] = meta['log_no']
        item['title'] = meta['title']
        item['filename'] = meta['filename']
        results[meta['log_no']] = item

    return results


def load_existing(output_path: Path) -> dict:
    if not output_path.exists():
        return {}
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_results(output_path: Path, results: dict, lock: Lock):
    with lock:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 deep_archive_extractor_batch.py <폴더> [출력JSON] [--parallel N] [--batch N]")
        sys.exit(1)

    dir_path = Path(sys.argv[1])
    output_path = None
    parallel = 3
    batch_size = 5
    model = "haiku"

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--parallel" and i + 1 < len(args):
            parallel = int(args[i + 1])
            i += 2
        elif args[i] == "--batch" and i + 1 < len(args):
            batch_size = int(args[i + 1])
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        else:
            output_path = Path(args[i])
            i += 1

    if output_path is None:
        output_path = dir_path.parent / "extracted_notes.json"

    print(f"=== 배치 추출 시작 ===", file=sys.stderr)
    print(f"입력: {dir_path}", file=sys.stderr)
    print(f"출력: {output_path}", file=sys.stderr)
    print(f"병렬: {parallel} / 배치: {batch_size}", file=sys.stderr)
    print(f"모델: {model} (Phase 1 구조 추출)", file=sys.stderr)
    print(f"", file=sys.stderr)

    files = sorted(dir_path.glob('*.md'))
    print(f"총 파일: {len(files)}", file=sys.stderr)

    results = load_existing(output_path)
    existing_log_nos = set(results.keys())
    print(f"이미 처리: {len(existing_log_nos)}", file=sys.stderr)

    # 미처리 파일만 추출
    pending = [f for f in files if extract_log_no(f.name) not in existing_log_nos]
    print(f"남은 작업: {len(pending)}", file=sys.stderr)
    print(f"", file=sys.stderr)

    if not pending:
        print("모두 처리 완료. 종료.", file=sys.stderr)
        return

    # 배치로 묶기
    batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]
    print(f"총 배치 수: {len(batches)} (병렬 {parallel})", file=sys.stderr)
    print(f"", file=sys.stderr)

    lock = Lock()
    completed_batches = 0
    total_ok = 0
    total_fail = 0
    consecutive_call_errors = 0
    CALL_ERROR_THRESHOLD = 5  # 5배치 연속 CLI 호출 실패 시 토큰 만료로 판단, exit 1
    start_time = time.time()
    aborted = False

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(process_batch, b, 2, model): i for i, b in enumerate(batches)}

        for future in as_completed(futures):
            if aborted:
                future.cancel()
                continue
            batch_idx = futures[future]
            try:
                batch_results = future.result()
                if batch_results.get("__call_error__"):
                    # CLI 호출 자체 실패
                    consecutive_call_errors += 1
                    total_fail += batch_size
                    if consecutive_call_errors >= CALL_ERROR_THRESHOLD:
                        print(f"  ✖ 연속 {CALL_ERROR_THRESHOLD}배치 CLI 호출 실패 (토큰 만료 추정). 중단.",
                              file=sys.stderr)
                        aborted = True
                        continue
                elif batch_results:
                    with lock:
                        results.update(batch_results)
                    total_ok += len(batch_results)
                    consecutive_call_errors = 0
                else:
                    total_fail += batch_size
                    consecutive_call_errors = 0  # 파싱 실패는 토큰 만료 아님
            except Exception as e:
                total_fail += batch_size
                print(f"  배치 {batch_idx} 예외: {e}", file=sys.stderr)

            completed_batches += 1

            # 5배치마다 저장
            if completed_batches % 5 == 0:
                save_results(output_path, results, lock)
                elapsed = time.time() - start_time
                rate = total_ok / max(elapsed, 1)
                remaining_files = len(pending) - total_ok
                eta = remaining_files / max(rate, 0.1)
                print(f"  [{completed_batches}/{len(batches)} 배치] OK {total_ok} / FAIL {total_fail} / 경과 {elapsed:.0f}s / ETA {eta:.0f}s",
                      file=sys.stderr)

    save_results(output_path, results, lock)

    print(f"", file=sys.stderr)
    print(f"=== {'중단' if aborted else '완료'} ===", file=sys.stderr)
    print(f"성공: {total_ok}", file=sys.stderr)
    print(f"실패: {total_fail}", file=sys.stderr)
    print(f"전체 누적: {len(results)}/{len(files)}", file=sys.stderr)

    if aborted:
        sys.exit(1)


if __name__ == "__main__":
    main()
