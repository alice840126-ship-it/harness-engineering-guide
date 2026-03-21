#!/usr/bin/env python3
"""
다중 위치 기록 에이전트

4곳 동시 기록 (work_log, session_log, shared_context, 옵시디언)
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiLocationRecorder:
    """다중 위치 기록 에이전트"""

    def __init__(
        self,
        work_log_path: Optional[Path] = None,
        session_log_path: Optional[Path] = None,
        shared_context_path: Optional[Path] = None,
        obsidian_vault_path: Optional[Path] = None
    ):
        """
        초기화

        Args:
            work_log_path: work_log.json 경로
            session_log_path: session_log.md 경로
            shared_context_path: shared_context.md 경로
            obsidian_vault_path: 옵시디언 볼트 경로
        """
        self.work_log_path = work_log_path or Path.home() / ".claude" / "work_log.json"
        self.session_log_path = session_log_path or Path.home() / ".claude" / "session_log.md"
        self.shared_context_path = shared_context_path or Path.home() / ".claude-unified" / "shared_context.md"
        self.obsidian_vault_path = obsidian_vault_path or (
            Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"
        )

        # 폴더 생성
        self.work_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.shared_context_path.parent.mkdir(parents=True, exist_ok=True)

    def record_to_4_locations(
        self,
        content: str,
        date: Optional[str] = None,
        source: str = "terminal"
    ) -> Dict[str, bool]:
        """
        4곳에 동시 기록

        Args:
            content: 기록할 내용
            date: 날짜 (YYYY-MM-DD, 기본: 오늘)
            source: 출처 (terminal, telegram)

        Returns:
            {location: success} 딕셔너리
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        results = {}

        # 1. work_log.json
        results["work_log"] = self.record_to_work_log(content, date)

        # 2. session_log.md
        results["session_log"] = self.record_to_session_log(content, date)

        # 3. shared_context.md
        results["shared_context"] = self.record_to_shared_context(content, date, source)

        # 4. 옵시디언 데일리 노트
        results["obsidian"] = self.record_to_obsidian_daily(content, date)

        return results

    def record_to_work_log(
        self,
        content: str,
        date: Optional[str] = None
    ) -> bool:
        """
        work_log.json에 기록

        Args:
            content: 기록할 내용
            date: 날짜 (YYYY-MM-DD)

        Returns:
            성공 여부
        """
        try:
            # 기존 데이터 로드
            if self.work_log_path.exists():
                with open(self.work_log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"current_session": [], "last_update": None}

            # 새 항목 추가
            now = datetime.now()
            entry = {
                "time": now.strftime("%H:%M"),
                "description": content,
                "status": "완료"
            }

            data["current_session"].append(entry)
            data["last_update"] = now.isoformat()

            # 저장
            with open(self.work_log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ work_log.json에 기록 완료")
            return True

        except Exception as e:
            logger.error(f"❌ work_log.json 기록 실패: {e}")
            return False

    def record_to_session_log(
        self,
        content: str,
        date: Optional[str] = None
    ) -> bool:
        """
        session_log.md에 기록

        Args:
            content: 기록할 내용
            date: 날짜 (YYYY-MM-DD)

        Returns:
            성공 여부
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"\n## [{timestamp}] {date} 기록\n\n{content}\n\n---\n"

            with open(self.session_log_path, 'a', encoding='utf-8') as f:
                f.write(entry)

            logger.info(f"✅ session_log.md에 기록 완료")
            return True

        except Exception as e:
            logger.error(f"❌ session_log.md 기록 실패: {e}")
            return False

    def record_to_shared_context(
        self,
        content: str,
        date: Optional[str] = None,
        source: str = "terminal"
    ) -> bool:
        """
        shared_context.md에 기록 (섹션별)

        Args:
            content: 기록할 내용
            date: 날짜 (YYYY-MM-DD)
            source: 출처 (terminal, telegram)

        Returns:
            성공 여부
        """
        try:
            # 섹션 결정
            if source in ["telegram", "텔레그램", "텔레봇"]:
                section_name = "### 텔레그램 봇"
            else:
                section_name = "### 터미널 (Claude Code)"

            # 기존 내용 읽기
            if self.shared_context_path.exists():
                with open(self.shared_context_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            else:
                file_content = f"# 공유 컨텍스트\n\n{section_name}\n\n"

            # 항목 생성
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"\n## {date} {timestamp}\n{content}\n"

            # 섹션 찾기
            if section_name in file_content:
                # 섹션 뒤에 추가
                parts = file_content.split(section_name, 1)
                if len(parts) == 2:
                    before = parts[0] + section_name
                    after = parts[1]

                    # 다음 섹션 찾기
                    next_section_idx = after.find("\n### ")
                    if next_section_idx > 0:
                        # 다음 섹션 전에 추가
                        insert_pos = next_section_idx + 1
                        new_content = before + after[:insert_pos] + entry + after[insert_pos:]
                    else:
                        # 다음 섹션이 없으면 끝에 추가
                        new_content = before + after + entry
                else:
                    new_content = file_content + entry
            else:
                # 섹션이 없으면 끝에 추가
                new_content = file_content + f"\n{section_name}\n" + entry

            # 저장
            with open(self.shared_context_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            logger.info(f"✅ shared_context.md에 기록 완료 ({section_name})")
            return True

        except Exception as e:
            logger.error(f"❌ shared_context.md 기록 실패: {e}")
            return False

    def record_to_obsidian_daily(
        self,
        content: str,
        date: Optional[str] = None
    ) -> bool:
        """
        옵시디언 데일리 노트에 기록

        Args:
            content: 기록할 내용
            date: 날짜 (YYYY-MM-DD)

        Returns:
            성공 여부
        """
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            daily_note_dir = self.obsidian_vault_path / "30. 자원 상자" / "01. 데일리 노트"
            daily_note_path = daily_note_dir / f"{date}.md"

            # 파일이 없으면 생성 안 함
            if not daily_note_path.exists():
                logger.info(f"⚠️ 옵시디언 데일리 노트 없음: {daily_note_path}")
                return False

            # 기존 내용 읽기
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # 작업 로그 섹션 확인
            if "## 작업 로그" not in file_content:
                logger.info(f"⚠️ 작업 로그 섹션 없음")
                return False

            # 23:00 저녁 자동 요약 섹션 확인
            if "### 🌙 저녁 23:00 자동 요약" in file_content:
                logger.info(f"⚠️ 이미 저녁 요약 섹션 존재")
                return False

            # 작업 로그 섹션 끝에 추가
            lines = file_content.split('\n')
            insert_idx = -1

            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "---" or i == len(lines) - 1:
                    insert_idx = i
                    break

            if insert_idx > 0:
                # 요약 추가
                timestamp = datetime.now().strftime("%H:%M")
                evening_entry = f"\n\n### 🌙 저녁 {timestamp} 자동 기록\n{content}\n"
                lines.insert(insert_idx, evening_entry)

                # 다시 합치기
                new_content = '\n'.join(lines)

                # 저장
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                logger.info(f"✅ 옵시디언 데일리 노트에 기록 완료")
                return True
            else:
                logger.info(f"⚠️ 삽입 위치 찾기 실패")
                return False

        except Exception as e:
            logger.error(f"❌ 옵시디언 기록 실패: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        4곳 기록 통계

        Returns:
            통계 정보 딕셔너리
        """
        stats = {
            "work_log": {
                "exists": self.work_log_path.exists(),
                "path": str(self.work_log_path)
            },
            "session_log": {
                "exists": self.session_log_path.exists(),
                "path": str(self.session_log_path)
            },
            "shared_context": {
                "exists": self.shared_context_path.exists(),
                "path": str(self.shared_context_path)
            },
            "obsidian": {
                "vault_exists": self.obsidian_vault_path.exists(),
                "vault_path": str(self.obsidian_vault_path)
            }
        }

        # work_log.json 항목 수
        if stats["work_log"]["exists"]:
            try:
                with open(self.work_log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stats["work_log"]["entries"] = len(data.get("current_session", []))
            except:
                stats["work_log"]["entries"] = 0

        return stats
