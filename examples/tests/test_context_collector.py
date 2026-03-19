#!/usr/bin/env python3
"""
ContextCollector 에이전트 단위 테스트
"""

import unittest
import tempfile
import json
from pathlib import Path
import sys
import os

# agents 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from context_collector import ContextCollector


class TestContextCollector(unittest.TestCase):
    """ContextCollector 단위 테스트"""

    def setUp(self):
        """테스트 설정"""
        # 임시 디렉토리 생성
        self.temp_dir = tempfile.mkdtemp()

        # 임시 파일 경로
        self.history_file = Path(self.temp_dir) / "history.jsonl"
        self.patterns_file = Path(self.temp_dir) / "patterns.json"
        self.context_file = Path(self.temp_dir) / "shared_context.md"

        # ContextCollector 초기화
        self.collector = ContextCollector(
            history_file=str(self.history_file),
            patterns_file=str(self.patterns_file),
            shared_context_path=str(self.context_file)
        )

        # 테스트용 세션 데이터 생성
        self.test_sessions = [
            {
                "timestamp": "2026-03-19T10:30:00",
                "messages": [
                    {"role": "user", "content": "내일 오전 10시로 예약해"},
                    {"role": "assistant", "content": "내일 오전 10시로 예약 완료했습니다."}
                ]
            },
            {
                "timestamp": "2026-03-19T11:00:00",
                "messages": [
                    {"role": "user", "content": "이 카페가 좋아. 여기가 제일 좋아."},
                    {"role": "assistant", "content": "알겠습니다. 이 카페를 선호하시는군요."}
                ]
            },
            {
                "timestamp": "2026-03-19T12:00:00",
                "messages": [
                    {"role": "user", "content": "매일 아침 명상하는 게 루틴이야"},
                    {"role": "assistant", "content": "매일 아침 명상 루틴을 기록했습니다."}
                ]
            }
        ]

    def test_collect_context_basic(self):
        """기본 컨텍스트 수집"""
        # 테스트 데이터 저장
        with open(self.history_file, 'w', encoding='utf-8') as f:
            for session in self.test_sessions:
                f.write(json.dumps(session) + '\n')

        # 컨텍스트 수집
        findings = self.collector.collect_context(limit=10)

        # 결과 확인
        self.assertIsInstance(findings, dict)
        self.assertIn("결정", findings)
        self.assertIn("선호도", findings)
        self.assertIn("패턴", findings)
        self.assertIn("인사이트", findings)

    def test_collect_decision_patterns(self):
        """결정 패턴 추출"""
        # 결정 패턴이 있는 세션
        session = {
            "timestamp": "2026-03-19T10:30:00",
            "messages": [
                {"role": "user", "content": "내일 오전 10시로 예약해"},
                {"role": "assistant", "content": "확정했습니다."}
            ]
        }

        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(session) + '\n')

        findings = self.collector.collect_context(limit=10)

        # 결정 패턴 확인
        self.assertGreater(len(findings["결정"]), 0)

    def test_collect_preference_patterns(self):
        """선호도 패턴 추출"""
        # 선호도 패턴이 있는 세션
        session = {
            "timestamp": "2026-03-19T11:00:00",
            "messages": [
                {"role": "user", "content": "이 카페가 좋아. 여기가 제일 좋아."},
                {"role": "assistant", "content": "알겠습니다."}
            ]
        }

        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(session) + '\n')

        findings = self.collector.collect_context(limit=10)

        # 선호도 패턴 확인
        self.assertGreater(len(findings["선호도"]), 0)

    def test_collect_routine_patterns(self):
        """반복 패턴 추출"""
        # 루틴 패턴이 있는 세션
        session = {
            "timestamp": "2026-03-19T12:00:00",
            "messages": [
                {"role": "user", "content": "매일 아침 명상하는 게 루틴이야"},
                {"role": "assistant", "content": "기록했습니다."}
            ]
        }

        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(session) + '\n')

        findings = self.collector.collect_context(limit=10)

        # 패턴 확인
        self.assertGreater(len(findings["패턴"]), 0)

    def test_custom_patterns(self):
        """커스텀 패턴 적용"""
        custom_patterns = {
            "투자": [
                r"(주식|코인)(.*?)(매수|매도)",
            ]
        }

        session = {
            "timestamp": "2026-03-19T13:00:00",
            "messages": [
                {"role": "user", "content": "삼성전자 주식 매수 결정"},
                {"role": "assistant", "content": "기록했습니다."}
            ]
        }

        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(session) + '\n')

        findings = self.collector.collect_context(patterns=custom_patterns, limit=10)

        # 커스텀 패턴이 적용되었는지 확인
        self.assertIn("투자", findings)

    def test_generate_insights(self):
        """인사이트 생성"""
        findings = {
            "결정": ["내일 오전 10시로 예약"],
            "선호도": ["이 카페가 좋아"],
            "패턴": ["매일 아침 명상"],
            "인사이트": []
        }

        insights = self.collector.generate_insights(findings)

        self.assertIn("### 최근 결정", insights)
        self.assertIn("### 선호도", insights)
        self.assertIn("### 반복 패턴", insights)
        self.assertIn("1개의 결정 패턴", insights)

    def test_save_patterns(self):
        """패턴 저장"""
        findings = {
            "결정": ["결정1"],
            "선호도": ["선호도1"],
            "패턴": [],
            "인사이트": []
        }

        self.collector.save_patterns(findings)

        # 파일이 생성되었는지 확인
        self.assertTrue(self.patterns_file.exists())

        # 내용 확인
        with open(self.patterns_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIsInstance(data, dict)
        # 오늘 날짜 키가 있는지 확인
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(today, data)

    def test_update_shared_context_new_section(self):
        """Shared Context 새 섹션 추가"""
        # 빈 context 파일 생성
        self.context_file.write_text("# 기존 내용\n", encoding='utf-8')

        insights = "### 최근 결정\n- 1개의 결정 패턴 발견\n"

        result = self.collector.update_shared_context(insights)

        self.assertTrue(result)

        # 파일 내용 확인
        content = self.context_file.read_text(encoding='utf-8')
        self.assertIn("## 학습된 패턴", content)

    def test_update_shared_context_existing_section(self):
        """Shared Context 기존 섹션 업데이트"""
        # 기존 섹션이 있는 context 파일 생성
        self.context_file.write_text(
            "# 기존 내용\n\n## 학습된 패턴\n\n기존 내용\n\n## 다른 섹션\n",
            encoding='utf-8'
        )

        insights = "### 최근 결정\n- 새로운 내용\n"

        result = self.collector.update_shared_context(insights)

        self.assertTrue(result)

        # 파일 내용 확인
        content = self.context_file.read_text(encoding='utf-8')
        self.assertIn("새로운 내용", content)

    def test_empty_history_file(self):
        """빈 history 파일 처리"""
        # 빈 파일 생성
        self.history_file.write_text("", encoding='utf-8')

        findings = self.collector.collect_context(limit=10)

        # 빈 결과 반환
        self.assertEqual(len(findings["결정"]), 0)
        self.assertEqual(len(findings["선호도"]), 0)


if __name__ == '__main__':
    # datetime import 추가
    from datetime import datetime
    unittest.main()
