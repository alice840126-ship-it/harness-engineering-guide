#!/usr/bin/env python3
"""
노션 작성 에이전트

Notion API를 통해 페이지를 생성/업데이트하는 재사용 가능한 에이전트
- 단일 책임: 노션에 콘텐츠 저장만 담당

사용법:
    python3 agents/notion_writer.py  # 테스트 실행

    from notion_writer import NotionWriter
    writer = NotionWriter()
    writer.create_page(database_id="xxx", title="제목", content="내용")
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_agent import BaseAgent, AgentError

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionWriter(BaseAgent):
    """Notion API 페이지 작성 에이전트"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="NotionWriter", config=config or {})
        self.api_key = os.getenv("NOTION_API_KEY", "")
        if not self.api_key:
            raise AgentError("NOTION_API_KEY 환경변수가 없습니다", self.name)

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    # ── 내부 HTTP 헬퍼 ──────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        url = f"{NOTION_API_BASE}/{path.lstrip('/')}"
        resp = requests.request(method, url, headers=self.headers, json=body)
        if not resp.ok:
            raise AgentError(f"Notion API 오류 {resp.status_code}: {resp.text}", self.name)
        return resp.json()

    # ── 공개 메서드 ─────────────────────────────────────────────────────────

    def list_databases(self) -> List[Dict]:
        """접근 가능한 데이터베이스 목록 반환"""
        result = self._request("POST", "/search", {
            "filter": {"value": "database", "property": "object"},
            "page_size": 50,
        })
        return result.get("results", [])

    def list_pages(self, database_id: str, page_size: int = 20) -> List[Dict]:
        """데이터베이스 내 페이지 목록"""
        result = self._request("POST", f"/databases/{database_id}/query", {
            "page_size": page_size,
        })
        return result.get("results", [])

    def get_page(self, page_id: str) -> Dict:
        """페이지 메타데이터 조회"""
        return self._request("GET", f"/pages/{page_id}")

    def create_page(
        self,
        database_id: str,
        title: str,
        content: str = "",
        properties: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """
        데이터베이스에 새 페이지 생성

        Args:
            database_id : 대상 데이터베이스 ID
            title       : 페이지 제목
            content     : 본문 (마크다운 줄바꿈 지원)
            properties  : 추가 프로퍼티 (dict)
            tags        : 멀티셀렉트 태그 리스트

        Returns:
            생성된 페이지 정보 dict
        """
        props: Dict[str, Any] = {
            "title": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        }
        if tags:
            props["태그"] = {"multi_select": [{"name": t} for t in tags]}
        if properties:
            props.update(properties)

        body: Dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": props,
        }

        # 본문 블록 추가
        if content:
            body["children"] = self._text_to_blocks(content)

        result = self._request("POST", "/pages", body)
        print(f"✅ 노션 페이지 생성: {title}")
        return result

    def append_content(self, page_id: str, content: str) -> Dict:
        """기존 페이지에 내용 추가"""
        blocks = self._text_to_blocks(content)
        result = self._request("PATCH", f"/blocks/{page_id}/children", {"children": blocks})
        print(f"✅ 노션 페이지 업데이트: {page_id}")
        return result

    def update_title(self, page_id: str, title: str) -> Dict:
        """페이지 제목 변경"""
        body = {
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            }
        }
        return self._request("PATCH", f"/pages/{page_id}", body)

    def create_standalone_page(self, parent_page_id: str, title: str, content: str = "") -> Dict:
        """데이터베이스 없이 일반 페이지 하위에 페이지 생성"""
        body: Dict[str, Any] = {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
        }
        if content:
            body["children"] = self._text_to_blocks(content)
        result = self._request("POST", "/pages", body)
        print(f"✅ 노션 페이지 생성: {title}")
        return result

    # ── 내부 유틸 ────────────────────────────────────────────────────────────

    def _text_to_blocks(self, text: str) -> List[Dict]:
        """텍스트를 Notion 블록 리스트로 변환 (단락 분리)"""
        blocks = []
        for line in text.split("\n"):
            line = line.rstrip()
            if line.startswith("# "):
                blocks.append(self._heading(line[2:], level=1))
            elif line.startswith("## "):
                blocks.append(self._heading(line[3:], level=2))
            elif line.startswith("### "):
                blocks.append(self._heading(line[4:], level=3))
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append(self._bullet(line[2:]))
            else:
                blocks.append(self._paragraph(line))
        return blocks

    @staticmethod
    def _paragraph(text: str) -> Dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    @staticmethod
    def _heading(text: str, level: int = 1) -> Dict:
        t = f"heading_{level}"
        return {
            "object": "block",
            "type": t,
            t: {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    @staticmethod
    def _bullet(text: str) -> Dict:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    # ── BaseAgent 필수 구현 ──────────────────────────────────────────────────

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        data 키:
            operation    : "create" | "append" | "list_db" | "list_pages"
            database_id  : 데이터베이스 ID (create/list_pages 시 필수)
            page_id      : 페이지 ID (append 시 필수)
            title        : 제목 (create 시 필수)
            content      : 본문 (선택)
            tags         : 태그 리스트 (선택)
        """
        op = data.get("operation", "create")

        if op == "list_db":
            dbs = self.list_databases()
            return {"databases": dbs, "count": len(dbs)}

        elif op == "list_pages":
            db_id = data["database_id"]
            pages = self.list_pages(db_id)
            return {"pages": pages, "count": len(pages)}

        elif op == "create":
            db_id = data.get("database_id")
            parent_id = data.get("parent_page_id")
            title = data.get("title", f"노트 {datetime.now().strftime('%Y-%m-%d')}")
            content = data.get("content", "")
            tags = data.get("tags", [])

            if db_id:
                page = self.create_page(db_id, title, content, tags=tags)
            elif parent_id:
                page = self.create_standalone_page(parent_id, title, content)
            else:
                raise AgentError("database_id 또는 parent_page_id 필요", self.name)

            return {"page_id": page["id"], "url": page.get("url", ""), "title": title}

        elif op == "append":
            page_id = data["page_id"]
            content = data.get("content", "")
            self.append_content(page_id, content)
            return {"page_id": page_id, "status": "appended"}

        else:
            raise AgentError(f"알 수 없는 operation: {op}", self.name)


# ── 테스트 실행 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    writer = NotionWriter()

    print("📋 접근 가능한 데이터베이스 목록:")
    dbs = writer.list_databases()
    if not dbs:
        print("  ⚠️  접근 가능한 데이터베이스가 없습니다.")
        print("  → Notion Integration에 페이지/DB를 공유했는지 확인하세요:")
        print("    노션 페이지 우측 상단 '...' → Connections → Integration 추가")
    else:
        for db in dbs:
            title = ""
            t = db.get("title", [])
            if t:
                title = t[0].get("plain_text", "")
            print(f"  - [{db['id']}] {title}")
