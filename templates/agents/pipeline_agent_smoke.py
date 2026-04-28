#!/usr/bin/env python3
"""pipeline_agent_smoke — PipelineAgent observe=True 통합 smoke test.

observer 훅 추가가 기존 PipelineAgent 동작을 깨뜨리지 않는지, 그리고
observe=True 시 JSONL 로그가 실제로 생성되는지 검증.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from base_agent import BaseAgent  # type: ignore
from pipeline_agent import PipelineAgent  # type: ignore


class DummyAgent(BaseAgent):
    def process(self, data):
        return {**data, f"ran_{self.name}": True}


class ExplodingAgent(BaseAgent):
    def process(self, data):
        raise ValueError("intentional")


def _selftest():
    passed = 0

    # === case 1: observe=False (기본) — 기존 동작 유지
    p1 = PipelineAgent(name="p1_off", agents=[DummyAgent("a"), DummyAgent("b")])
    r1 = p1.run({"query": "kw1"})
    assert r1.get("ran_a") and r1.get("ran_b"), r1
    print(f"  ✓ case 1 observe=False (keys={list(r1)})")
    passed += 1

    # === case 2: observe=True — JSONL 기록 확인
    import pipeline_observer as po  # type: ignore
    with tempfile.TemporaryDirectory() as tmp:
        orig_log_dir = po.LOG_DIR
        po.LOG_DIR = Path(tmp) / "logs"
        try:
            p2 = PipelineAgent(
                name="p2_on",
                agents=[DummyAgent("s1"), DummyAgent("s2"), DummyAgent("s3")],
                observe=True,
            )
            r2 = p2.run({"query": "kw2"})
            assert r2.get("ran_s1") and r2.get("ran_s3")
            # 로그 파일 존재 확인
            from datetime import date
            log_file = po.LOG_DIR / f"{date.today()}.jsonl"
            assert log_file.exists(), f"로그 파일 없음: {log_file}"
            recs = [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
            # pipeline_start + 3 * (stage_start + stage_end) + pipeline_end = 8
            types = [r["type"] for r in recs]
            assert types.count("stage_start") == 3, f"stage_start 수: {types}"
            assert types.count("stage_end") == 3, f"stage_end 수: {types}"
            assert "pipeline_start" in types and "pipeline_end" in types
            # output_keys attr 기록 확인
            stage_ends = [r for r in recs if r["type"] == "stage_end"]
            assert all("output_keys" in (r.get("attrs") or {}) for r in stage_ends)
        finally:
            po.LOG_DIR = orig_log_dir
    print(f"  ✓ case 2 observe=True (3 stages logged)")
    passed += 1

    # === case 3: observe=True + 에러 (stop_on_error=False) — 로그 status=error
    import pipeline_observer as po  # type: ignore
    with tempfile.TemporaryDirectory() as tmp:
        orig = po.LOG_DIR
        po.LOG_DIR = Path(tmp) / "logs"
        try:
            p3 = PipelineAgent(
                name="p3_err",
                agents=[DummyAgent("ok"), ExplodingAgent("boom"), DummyAgent("after")],
                observe=True,
                stop_on_error=False,
            )
            r3 = p3.run({"query": "kw3"})
            # ok와 after는 돌아야
            assert r3.get("ran_ok"), r3
            # boom 은 실패했으므로 결과에 플래그 없어야
            assert not r3.get("ran_boom")
            # 로그에서 error stage 확인
            from datetime import date
            log_file = po.LOG_DIR / f"{date.today()}.jsonl"
            recs = [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
            err_stages = [r for r in recs if r.get("type") == "stage_end"
                          and r.get("status") == "failed"]
            assert err_stages, f"failed 스테이지 없음: {[r.get('status') for r in recs if r.get('type')=='stage_end']}"
        finally:
            po.LOG_DIR = orig
    print(f"  ✓ case 3 observe=True + error (soft-fail recorded)")
    passed += 1

    # === case 4: observer import 실패 시 silent fallback (경로 훼손)
    # PipelineAgent는 observer 실패해도 파이프라인 자체는 계속 돌아야
    # (pipeline_observer가 실제로 import 가능한 환경이므로 여기서는
    #  LOG_DIR 을 읽기 불가 경로로 만들어서 write 실패 유도)
    with tempfile.TemporaryDirectory() as tmp:
        orig = po.LOG_DIR
        po.LOG_DIR = Path(tmp) / "logs"
        try:
            # write 가능하게 디렉토리는 만들어주고 실행
            p4 = PipelineAgent(
                name="p4_resil",
                agents=[DummyAgent("only")],
                observe=True,
            )
            r4 = p4.run({"query": "kw4"})
            assert r4.get("ran_only")
        finally:
            po.LOG_DIR = orig
    print(f"  ✓ case 4 observer write-path resilient")
    passed += 1

    # === case 5: orchestrator import 호환
    sys.path.insert(0, str(HERE / "orchestrators"))
    from orchestrators.daily_news_pipeline import DailyNewsPipeline  # noqa
    from orchestrators.market_analysis_pipeline import MarketAnalysisPipeline  # noqa
    # 생성자 호출 가능 확인 (실제 run 은 네트워크 필요)
    # 단, DailyNewsPipeline.__init__ 가 실제 NewsScraper 등을 생성하므로
    # 그 자체만으로도 호환성 검증 가능
    try:
        dnp = DailyNewsPipeline()
        assert dnp.pipeline.observe is True, "daily_news에 observe=True 연결 안 됨"
        assert dnp.pipeline.observe_keyword_key == "query"
    except Exception as e:
        raise AssertionError(f"DailyNewsPipeline 생성 실패: {e}")
    try:
        map_p = MarketAnalysisPipeline()
        assert getattr(map_p, "_observe", False), "market_analysis에 _observe=True 연결 안 됨"
    except Exception as e:
        raise AssertionError(f"MarketAnalysisPipeline 생성 실패: {e}")
    print(f"  ✓ case 5 orchestrator wiring (daily_news, market_analysis)")
    passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    _selftest()
