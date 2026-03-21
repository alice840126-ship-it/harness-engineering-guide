#!/usr/bin/env python3
"""
BaseAgent - 표준 에이전트 인터페이스

모든 에이전트가 따라야 할 표준 인터페이스와 공통 기능을 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os


class AgentError(Exception):
    """에이전트 에러 기본 클래스"""

    def __init__(self, message: str, agent_name: str, details: Optional[Dict] = None):
        self.message = message
        self.agent_name = agent_name
        self.details = details or {}
        super().__init__(f"[{agent_name}] {message}")


class BaseAgent(ABC):
    """
    표준 에이전트 인터페이스

    모든 에이전트는 이 클래스를 상속받아야 합니다.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            name: 에이전트 이름
            config: 에이전트 설정 (선택)
        """
        self.name = name
        self.config = config or {}
        self._stats = {
            "runs": 0,
            "errors": 0,
            "last_run": None
        }

    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 처리 (필수 구현)

        Args:
            data: 입력 데이터

        Returns:
            처리 결과 데이터

        Raises:
            AgentError: 처리 중 에러 발생
        """
        pass

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        입력 데이터 검증 (선택 오버라이드)

        Args:
            data: 검증할 데이터

        Returns:
            유효 여부
        """
        return isinstance(data, dict)

    def validate_output(self, data: Dict[str, Any]) -> bool:
        """
        출력 데이터 검증 (선택 오버라이드)

        Args:
            data: 검증할 데이터

        Returns:
            유효 여부
        """
        return isinstance(data, dict)

    def log_error(self, error: Exception, context: Optional[Dict] = None):
        """
        에러 로깅

        Args:
            error: 발생한 에러
            context: 추가 컨텍스트
        """
        self._stats["errors"] += 1

        error_info = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }

        # 환경변수로 로깅 방식 결정
        if os.getenv("AGENT_LOG_TO_FILE") == "true":
            self._log_to_file(error_info)
        else:
            print(f"❌ [{self.name}] {error_info['error_type']}: {error_info['error_message']}")

    def _log_to_file(self, error_info: Dict):
        """파일에 로그 기록"""
        log_dir = os.getenv("AGENT_LOG_DIR", ".agent_logs")
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f"{self.name}_errors.jsonl")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_info, ensure_ascii=False) + "\n")

    def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        실행 (검증 + 처리 + 검증)

        Args:
            data: 입력 데이터

        Returns:
            처리 결과
        """
        try:
            # 입력 검증
            if not self.validate_input(data):
                raise ValueError("입력 데이터가 유효하지 않습니다")

            # 처리
            result = self.process(data)

            # 출력 검증
            if not self.validate_output(result):
                raise ValueError("출력 데이터가 유효하지 않습니다")

            # 통계 업데이트
            self._stats["runs"] += 1
            self._stats["last_run"] = datetime.now().isoformat()

            return result

        except Exception as e:
            self.log_error(e, context={"input_keys": list(data.keys())})
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        에이전트 통계 반환

        Returns:
            통계 정보
        """
        return self._stats.copy()

    def reset_stats(self):
        """통계 초기화"""
        self._stats = {
            "runs": 0,
            "errors": 0,
            "last_run": None
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
