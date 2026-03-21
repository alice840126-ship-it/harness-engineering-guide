#!/usr/bin/env python3
"""
BaseAgent 단위 테스트
"""

import pytest
from base_agent import BaseAgent, AgentError


class DummyAgent(BaseAgent):
    """테스트용 더미 에이전트"""

    def __init__(self, config=None):
        super().__init__("dummy", config)
        self.process_called = False

    def process(self, data):
        self.process_called = True
        return {"result": data.get("input", "") * 2}


class TestBaseAgent:
    """BaseAgent 테스트"""

    def test_init(self):
        """초기화 테스트"""
        agent = DummyAgent()
        assert agent.name == "dummy"
        assert agent.config == {}
        assert agent.get_stats()["runs"] == 0

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        config = {"setting1": "value1"}
        agent = DummyAgent(config)
        assert agent.config == config

    def test_process_method(self):
        """process 메서드 테스트"""
        agent = DummyAgent()
        result = agent.process({"input": "test"})
        assert result == {"result": "testtest"}

    def test_run_valid_input(self):
        """유효한 입력으로 실행"""
        agent = DummyAgent()
        result = agent.run({"input": "hello"})
        assert result == {"result": "hellohello"}
        assert agent.get_stats()["runs"] == 1

    def test_run_invalid_input(self):
        """잘못된 입력으로 실행"""
        agent = DummyAgent()
        with pytest.raises(Exception):
            agent.run("not_a_dict")  # dict가 아님

    def test_validate_input_default(self):
        """기본 입력 검증"""
        agent = DummyAgent()
        assert agent.validate_input({"key": "value"}) is True
        assert agent.validate_input("not_dict") is False

    def test_validate_output_default(self):
        """기본 출력 검증"""
        agent = DummyAgent()
        assert agent.validate_output({"key": "value"}) is True
        assert agent.validate_output("not_dict") is False

    def test_error_logging(self):
        """에러 로깅 테스트"""
        agent = DummyAgent()

        try:
            agent.run("invalid_input")
        except:
            pass

        stats = agent.get_stats()
        assert stats["errors"] == 1

    def test_stats_tracking(self):
        """통계 추적 테스트"""
        agent = DummyAgent()

        # 초기 통계
        stats = agent.get_stats()
        assert stats["runs"] == 0
        assert stats["errors"] == 0

        # 실행 후 통계
        agent.run({"input": "test"})
        stats = agent.get_stats()
        assert stats["runs"] == 1
        assert stats["last_run"] is not None

    def test_reset_stats(self):
        """통계 초기화 테스트"""
        agent = DummyAgent()

        agent.run({"input": "test"})

        try:
            agent.run("invalid")
        except:
            pass

        # 에러 발생 확인
        assert agent.get_stats()["errors"] > 0

        # 초기화
        agent.reset_stats()
        stats = agent.get_stats()
        assert stats["runs"] == 0
        assert stats["errors"] == 0
        assert stats["last_run"] is None

    def test_repr(self):
        """문자열 표현 테스트"""
        agent = DummyAgent()
        assert repr(agent) == "DummyAgent(name='dummy')"


class TestAgentError:
    """AgentError 테스트"""

    def test_error_creation(self):
        """에러 생성 테스트"""
        error = AgentError("Test error", "test_agent")
        assert str(error) == "[test_agent] Test error"
        assert error.agent_name == "test_agent"
        assert error.message == "Test error"

    def test_error_with_details(self):
        """상세 정보와 함께 에러 생성"""
        details = {"context": "test_context"}
        error = AgentError("Test error", "test_agent", details)
        assert error.details == details
