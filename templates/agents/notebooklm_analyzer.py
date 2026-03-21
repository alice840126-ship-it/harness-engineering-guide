#!/usr/bin/env python3
"""
NotebookLM 분석 에이전트

NotebookLM CLI를 활용한 뉴스/문서 분석
"""

import json
import logging
import subprocess
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotebookLMAnalyzer:
    """NotebookLM 분석 에이전트"""

    def __init__(self, notebooklm_path: Optional[str] = "notebooklm", timeout: int = 600):
        """
        초기화

        Args:
            notebooklm_path: NotebookLM CLI 경로 (기본: notebooklm)
            timeout: 실행 타임아웃 (초)
        """
        self.notebooklm_path = notebooklm_path
        self.timeout = timeout

    def analyze_with_prompt(
        self,
        sources: List[str],
        prompt: str,
        json_output: bool = True
    ) -> Optional[Any]:
        """
        프롬프트 기반 분석

        Args:
            sources: 소스 파일/URL 리스트
            prompt: 분석 프롬프트
            json_output: JSON 출력 여부

        Returns:
            분석 결과 (실패 시 None)
        """
        try:
            # 명령어 구성
            cmd = [self.notebooklm_path, "ask", prompt]

            if json_output:
                cmd.append("--json")

            # NotebookLM 실행
            logger.info(f"🧠 NotebookLM 분석 시작...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                if json_output:
                    try:
                        return json.loads(result.stdout)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON 파싱 실패: {e}")
                        return result.stdout  # 텍스트 반환
                else:
                    return result.stdout
            else:
                logger.error(f"❌ NotebookLM 분석 실패: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("❌ NotebookLM 분석 시간 초과")
            return None
        except FileNotFoundError:
            logger.error(f"❌ NotebookLM CLI를 찾을 수 없음: {self.notebooklm_path}")
            return None
        except Exception as e:
            logger.error(f"❌ NotebookLM 분석 오류: {e}")
            return None

    def analyze_news_trends(
        self,
        news_items: List[Dict[str, str]],
        framework: str = "deep_insight"
    ) -> Optional[Dict[str, Any]]:
        """
        뉴스 트렌드 분석

        Args:
            news_items: 뉴스 아이템 리스트
                [{title, url, description, ...}]
            framework: 분석 프레임워크
                - deep_insight: 표면 → 진짜 타겟 → 숨겨진 의도
                - trend: 트렌드 분석
                - summary: 요약

        Returns:
            분석 결과 딕셔너리
        """
        # 프레임워크별 프롬프트
        prompts = {
            "deep_insight": """
다음 뉴스를 3층 구조로 깊이 분석해주세요:

### 1층: 표면적 사건 (Surface)
- 뉴스에 그대로 나오는 사건
- 대중이 보는 현상

### 2층: 진짜 타겟 (Real Target)
- 표면적 사건 뒤에 숨겨진 진짜 피해자/수혜자
- 실제로 영향을 받는 국가/기업/집단

### 3층: 숨겨진 의도 (Hidden Agenda)
- 왜 지금 이 타이밍인가?
- 진짜 목표는 무엇인가?
- 누가 이득을 보는가?

마지막으로 "미국이 이란을 쳤는데, 진짜 맞은 건 러시아다" 같은 깊은 통찰을 한 문장으로 정리해주세요.
""",
            "trend": """
다음 뉴스의 트렌드를 분석해주세요:
1. 주요 키워드 추출
2. 트렌드 그룹핑
3. 시사점 도출
""",
            "summary": """
다음 뉴스를 요약해주세요:
1. 주요 내용 3개
2. 핵심 인사이트
"""
        }

        prompt = prompts.get(framework, prompts["summary"])

        # 뉴스 아이템을 텍스트로 변환
        news_text = self._format_news_items(news_items)

        # 프롬프트에 뉴스 추가
        full_prompt = f"{prompt}\n\n## 뉴스\n\n{news_text}"

        # 분석
        return self.analyze_with_prompt([], full_prompt, json_output=True)

    def generate_deep_insight(
        self,
        sources: List[str],
        timeframe: str = "30일"
    ) -> Optional[str]:
        """
        깊은 통찰 생성

        Args:
            sources: 소스 리스트
            timeframe: 분석 기간

        Returns:
            인사이트 텍스트
        """
        prompt = f"""
지난 {timeframe}간의 주요 이슈를 분석하여 다음 질문에 답해주세요:

1. **주도권 누구에게?:**
   - 한국의 주도권은 있었는가?
   - 미국/중국 사이에서 어떤 위치?

2. **구조적 변화:**
   - 단순 일회성 사건이 아니라 구조적으로 변화된 것은?
   - 3개월 후, 1년 후 영향이 지속될 것은?

3. **선택 강요의 딜레마:**
   - 한국에게 어떤 선택을 강요하고 있는가?
   - 어느 쪽도 완벽하지 않은 상황인가?

마지막으로 **"미국이 이란을 쳤는데, 진짜 맞은 건 러시아다"** 같은 깊은 통찰을 한 문장으로 정리해주세요.
"""

        result = self.analyze_with_prompt(sources, prompt, json_output=False)

        if result:
            return str(result)
        else:
            return None

    def save_to_obsidian(
        self,
        analysis: Any,
        vault_path: Path,
        filename: str,
        title: str = "NotebookLM 분석"
    ) -> Optional[Path]:
        """
        분석 결과를 옵시디언에 저장

        Args:
            analysis: 분석 결과
            vault_path: 옵시디언 볼트 경로
            filename: 파일 이름
            title: 분석 제목

        Returns:
            저장된 파일 경로
        """
        try:
            # 분석 결과를 Markdown으로 변환
            md_content = self._format_analysis_to_md(analysis, title)

            # 파일 경로
            file_path = vault_path / filename

            # 폴더 생성
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            logger.info(f"✅ 옵시디언 저장 완료: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"❌ 옵시디언 저장 실패: {e}")
            return None

    def _format_news_items(self, news_items: List[Dict[str, str]]) -> str:
        """
        뉴스 아이템을 텍스트로 포맷팅

        Args:
            news_items: 뉴스 아이템 리스트

        Returns:
            포맷팅된 텍스트
        """
        lines = []

        for i, item in enumerate(news_items, 1):
            title = item.get("title", "")
            description = item.get("description", "")
            url = item.get("url", "")

            lines.append(f"{i}. **{title}**")
            if description:
                lines.append(f"   {description[:200]}...")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")

        return "\n".join(lines)

    def _format_analysis_to_md(self, analysis: Any, title: str) -> str:
        """
        분석 결과를 Markdown으로 변환

        Args:
            analysis: 분석 결과
            title: 제목

        Returns:
            Markdown 텍스트
        """
        timestamp = datetime.now().strftime('%Y년 %m월 %d일')

        if isinstance(analysis, dict):
            # 딕셔너리인 경우
            content = json.dumps(analysis, ensure_ascii=False, indent=2)
            return f"""# {title}

> **분석일:** {timestamp}
> **도구:** NotebookLM

```json
{content}
```

---

**분석일:** {timestamp}
**목적:** NotebookLM을 활용한 깊은 통찰 분석
"""
        else:
            # 텍스트인 경우
            return f"""# {title}

> **분석일:** {timestamp}

---

{analysis}

---

**분석일:** {timestamp}
**목적:** NotebookLM을 활용한 깊은 통찰 분석
"""

    def is_available(self) -> bool:
        """
        NotebookLM CLI 사용 가능 여부 확인

        Returns:
            사용 가능 여부
        """
        try:
            result = subprocess.run(
                [self.notebooklm_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
