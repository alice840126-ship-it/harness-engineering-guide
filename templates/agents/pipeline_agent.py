#!/usr/bin/env python3
"""
PipelineAgent - 에이전트 파이프라인 오케스트레이션

여러 에이전트를 순차적으로 실행하여 복잡한 작업을 수행합니다.
"""

from typing import List, Dict, Any, Optional, Callable
from copy import deepcopy
from base_agent import BaseAgent, AgentError


class PipelineAgent(BaseAgent):
    """
    파이프라인 에이전트

    여러 에이전트를 순서대로 연결하여 실행합니다.
    """

    def __init__(
        self,
        name: str,
        agents: List[BaseAgent],
        stop_on_error: bool = True,
        config: Optional[Dict[str, Any]] = None,
        observe: bool = False,
        observe_keyword_key: str = "query",
    ):
        """
        초기화

        Args:
            name: 파이프라인 이름
            agents: 실행할 에이전트 리스트
            stop_on_error: 에러 발생 시 중지 여부 (False면 계속 실행)
            config: 추가 설정
            observe: True 시 pipeline_observer로 JSONL 관찰성 기록
            observe_keyword_key: 입력 dict에서 keyword로 쓸 key명 (로깅용)
        """
        super().__init__(name, config)
        self.agents = agents
        self.stop_on_error = stop_on_error
        self.observe = observe
        self.observe_keyword_key = observe_keyword_key

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        파이프라인 실행

        Args:
            data: 초기 입력 데이터

        Returns:
            최종 결과 데이터
        """
        # --- observer 준비 (lazy import — 순환 참조 방지) ---
        obs = None
        if self.observe:
            try:
                import sys as _sys
                from pathlib import Path as _Path
                _sys.path.insert(0, str(_Path(__file__).resolve().parent))
                from pipeline_observer import PipelineObserver  # type: ignore
                kw = str(data.get(self.observe_keyword_key, ""))[:100]
                obs = PipelineObserver(pipeline=self.name, keyword=kw)
            except Exception as _e:
                # observer 실패는 본 파이프라인을 막지 않는다
                import sys as _sys
                _sys.stderr.write(f"[pipeline_observer disabled] {_e}\n")
                obs = None

        result = deepcopy(data)
        status = "ok"

        try:
            for i, agent in enumerate(self.agents):
                if obs is not None:
                    with obs.stage(agent.name) as s:
                        try:
                            result = agent.run(result)
                            # 스테이지 출력 요약 속성
                            s.attrs(output_keys=list(result.keys())[:10])
                            if self.config.get("save_intermediate", False):
                                result[f"_after_{agent.name}"] = deepcopy(result)
                        except Exception as e:
                            s.fail(f"{type(e).__name__}: {e}")
                            if self.stop_on_error:
                                status = "error"
                                raise AgentError(
                                    f"파이프라인 실행 실패 (단계 {i+1}/{len(self.agents)}: {agent.name})",
                                    self.name,
                                    {"stage": i, "agent": agent.name, "error": str(e)}
                                )
                            else:
                                print(f"⚠️ [{self.name}] {agent.name} 실패, 계속 실행")
                else:
                    try:
                        result = agent.run(result)
                        if self.config.get("save_intermediate", False):
                            result[f"_after_{agent.name}"] = deepcopy(result)
                    except Exception as e:
                        if self.stop_on_error:
                            status = "error"
                            raise AgentError(
                                f"파이프라인 실행 실패 (단계 {i+1}/{len(self.agents)}: {agent.name})",
                                self.name,
                                {"stage": i, "agent": agent.name, "error": str(e)}
                            )
                        else:
                            print(f"⚠️ [{self.name}] {agent.name} 실패, 계속 실행")
        finally:
            if obs is not None:
                obs.close(status)

        return result

    def add_agent(self, agent: BaseAgent):
        """
        파이프라인에 에이전트 추가

        Args:
            agent: 추가할 에이전트
        """
        self.agents.append(agent)

    def remove_agent(self, agent_name: str) -> bool:
        """
        파이프라인에서 에이전트 제거

        Args:
            agent_name: 제거할 에이전트 이름

        Returns:
            제거 성공 여부
        """
        for i, agent in enumerate(self.agents):
            if agent.name == agent_name:
                self.agents.pop(i)
                return True
        return False

    def get_agents(self) -> List[str]:
        """
        파이프라인의 에이전트 목록 반환

        Returns:
            에이전트 이름 리스트
        """
        return [agent.name for agent in self.agents]


class ConditionalPipelineAgent(BaseAgent):
    """
    조건부 파이프라인 에이전트

    조건에 따라 다른 에이전트를 실행합니다.
    """

    def __init__(
        self,
        name: str,
        branches: Dict[str, List[BaseAgent]],
        condition: Callable[[Dict[str, Any]], str],
        config: Optional[Dict[str, Any]] = None
    ):
        """
        초기화

        Args:
            name: 파이프라인 이름
            branches: 조건별 에이전트分支 {"condition_name": [agents]}
            condition: 조건 판별 함수 (데이터 -> 분기명)
            config: 추가 설정
        """
        super().__init__(name, config)
        self.branches = {k: PipelineAgent(f"{name}_{k}", v) for k, v in branches.items()}
        self.condition = condition

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        조건부 파이프라인 실행

        Args:
            data: 입력 데이터

        Returns:
            처리 결과
        """
        # 조건 판별
        branch_name = self.condition(data)

        if branch_name not in self.branches:
            raise AgentError(
                f"잘못된 분기: {branch_name}",
                self.name,
                {"available_branches": list(self.branches.keys())}
            )

        # 해당 분기 실행
        pipeline = self.branches[branch_name]
        return pipeline.run(data)


class ParallelPipelineAgent(BaseAgent):
    """
    병렬 파이프라인 에이전트

    여러 에이전트를 병렬로 실행하고 결과를 모읍니다.
    """

    def __init__(
        self,
        name: str,
        agents: List[BaseAgent],
        merge_strategy: str = "combine",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        초기화

        Args:
            name: 파이프라인 이름
            agents: 병렬 실행할 에이전트 리스트
            merge_strategy: 결과 병합 방식 ("combine", "first", "all")
            config: 추가 설정
        """
        super().__init__(name, config)
        self.agents = agents
        self.merge_strategy = merge_strategy

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        병렬 파이프라인 실행

        Args:
            data: 입력 데이터

        Returns:
            병합된 결과
        """
        results = {}

        for agent in self.agents:
            try:
                result = agent.run(data)
                results[agent.name] = result
            except Exception as e:
                print(f"⚠️ [{self.name}] {agent.name} 실패: {e}")
                if self.merge_strategy == "first":
                    raise

        # 병합 전략에 따라 결과 반환
        if self.merge_strategy == "combine":
            # 모든 결과를 하나로 합침
            combined = {}
            for result in results.values():
                combined.update(result)
            return combined

        elif self.merge_strategy == "first":
            # 첫 번째 성공한 결과 반환
            return next(iter(results.values()))

        elif self.merge_strategy == "all":
            # 모든 결과를 리스트로 반환
            return {"_parallel_results": results}

        else:
            raise ValueError(f"잘못된 병합 전략: {self.merge_strategy}")
