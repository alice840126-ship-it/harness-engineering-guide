#!/usr/bin/env python3
"""
PipelineAgent 단위 테스트
"""

import pytest
from base_agent import BaseAgent
from pipeline_agent import PipelineAgent, ConditionalPipelineAgent, ParallelPipelineAgent


class AddAgent(BaseAgent):
    """더하기 에이전트"""

    def __init__(self):
        super().__init__("add")

    def process(self, data):
        value = data.get("value", 0)
        return {"value": value + 10}


class MultiplyAgent(BaseAgent):
    """곱하기 에이전트"""

    def __init__(self):
        super().__init__("multiply")

    def process(self, data):
        value = data.get("value", 0)
        return {"value": value * 2}


class FailingAgent(BaseAgent):
    """실패하는 에이전트"""

    def __init__(self):
        super().__init__("failing")

    def process(self, data):
        raise ValueError("Intentional error")


class TestPipelineAgent:
    """PipelineAgent 테스트"""

    def test_init(self):
        """초기화 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        assert pipeline.name == "test_pipeline"
        assert len(pipeline.agents) == 2
        assert pipeline.stop_on_error is True

    def test_init_with_stop_on_error_false(self):
        """에러 시 계속 실행 설정"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents, stop_on_error=False)

        assert pipeline.stop_on_error is False

    def test_run_sequential(self):
        """순차 실행 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        result = pipeline.run({"value": 5})
        # 5 + 10 = 15, 15 * 2 = 30
        assert result["value"] == 30

    def test_get_agents(self):
        """에이전트 목록 반환 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        agent_names = pipeline.get_agents()
        assert agent_names == ["add", "multiply"]

    def test_add_agent(self):
        """에이전트 추가 테스트"""
        agents = [AddAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        assert len(pipeline.agents) == 1

        pipeline.add_agent(MultiplyAgent())
        assert len(pipeline.agents) == 2
        assert pipeline.get_agents() == ["add", "multiply"]

    def test_remove_agent(self):
        """에이전트 제거 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        assert pipeline.remove_agent("multiply") is True
        assert len(pipeline.agents) == 1
        assert pipeline.get_agents() == ["add"]

    def test_remove_nonexistent_agent(self):
        """존재하지 않는 에이전트 제거 시도"""
        agents = [AddAgent()]
        pipeline = PipelineAgent("test_pipeline", agents)

        assert pipeline.remove_agent("nonexistent") is False

    def test_stop_on_error_true(self):
        """에러 발생 시 중지"""
        agents = [AddAgent(), FailingAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents, stop_on_error=True)

        with pytest.raises(Exception):
            pipeline.run({"value": 5})

    def test_stop_on_error_false(self):
        """에러가 발생해도 계속 실행"""
        agents = [AddAgent(), FailingAgent(), MultiplyAgent()]
        pipeline = PipelineAgent("test_pipeline", agents, stop_on_error=False)

        # 에러가 발생하지만 계속 실행
        result = pipeline.run({"value": 5})
        # AddAgent: 5 + 10 = 15, FailingAgent 실패, MultiplyAgent: 15 * 2 = 30
        assert result["value"] == 30


class TestConditionalPipelineAgent:
    """ConditionalPipelineAgent 테스트"""

    def test_init(self):
        """초기화 테스트"""
        branches = {
            "branch1": [AddAgent()],
            "branch2": [MultiplyAgent()]
        }

        def condition(data):
            return "branch1"

        pipeline = ConditionalPipelineAgent("test_pipeline", branches, condition)

        assert pipeline.name == "test_pipeline"
        assert "branch1" in pipeline.branches
        assert "branch2" in pipeline.branches

    def test_run_branch1(self):
        """branch1 실행 테스트"""
        branches = {
            "add": [AddAgent()],
            "multiply": [MultiplyAgent()]
        }

        def condition(data):
            return "add"

        pipeline = ConditionalPipelineAgent("test_pipeline", branches, condition)

        result = pipeline.run({"value": 5})
        assert result["value"] == 15  # 5 + 10

    def test_run_branch2(self):
        """branch2 실행 테스트"""
        branches = {
            "add": [AddAgent()],
            "multiply": [MultiplyAgent()]
        }

        def condition(data):
            return "multiply"

        pipeline = ConditionalPipelineAgent("test_pipeline", branches, condition)

        result = pipeline.run({"value": 5})
        assert result["value"] == 10  # 5 * 2

    def test_invalid_branch(self):
        """잘못된 분기 실행 시도"""
        branches = {
            "add": [AddAgent()]
        }

        def condition(data):
            return "nonexistent"

        pipeline = ConditionalPipelineAgent("test_pipeline", branches, condition)

        with pytest.raises(Exception):
            pipeline.run({"value": 5})


class TestParallelPipelineAgent:
    """ParallelPipelineAgent 테스트"""

    def test_init(self):
        """초기화 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = ParallelPipelineAgent("test_pipeline", agents)

        assert pipeline.name == "test_pipeline"
        assert len(pipeline.agents) == 2
        assert pipeline.merge_strategy == "combine"

    def test_run_combine_strategy(self):
        """combine 병합 전략 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = ParallelPipelineAgent("test_pipeline", agents, merge_strategy="combine")

        result = pipeline.run({"value": 5})
        # 두 에이전트 결과가 합쳐짐 (마지막 값이 덮어씀)
        assert "value" in result

    def test_run_first_strategy(self):
        """first 병합 전략 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = ParallelPipelineAgent("test_pipeline", agents, merge_strategy="first")

        result = pipeline.run({"value": 5})
        # 첫 번째 성공한 결과
        assert "value" in result

    def test_run_all_strategy(self):
        """all 병합 전략 테스트"""
        agents = [AddAgent(), MultiplyAgent()]
        pipeline = ParallelPipelineAgent("test_pipeline", agents, merge_strategy="all")

        result = pipeline.run({"value": 5})
        # 모든 결과가 리스트로 반환
        assert "_parallel_results" in result
        assert "add" in result["_parallel_results"]
        assert "multiply" in result["_parallel_results"]

    def test_invalid_merge_strategy(self):
        """잘못된 병합 전략 테스트"""
        agents = [AddAgent()]
        pipeline = ParallelPipelineAgent("test_pipeline", agents, merge_strategy="invalid")

        with pytest.raises(ValueError):
            pipeline.run({"value": 5})
