#!/usr/bin/env python3
"""
중복 필터 에이전트 v2 (BaseAgent 기반)

URL/제목/ID 기반 중복 제거 시스템
- 단일 책임: 중복 필터링만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from base_agent import BaseAgent


class DuplicateFilter(BaseAgent):
    """중복 필터 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (db_path, max_entries)
        """
        super().__init__("duplicate_filter", config)

        self.db_path = Path(self.config.get("db_path",
            Path.home() / ".claude" / "duplicate_filter.json"))
        self.max_entries = self.config.get("max_entries", 100)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "check")

        if operation == "check":
            return "item" in data
        elif operation == "add":
            return "item" in data
        elif operation == "filter":
            return "items" in data
        elif operation == "stats":
            return True
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        중복 필터 처리

        Args:
            data: {
                "operation": str,    # "check", "add", "filter", "stats", "clear"
                "item": str,         # check/add용
                "items": list,       # filter용
                "category": str,     # 카테고리 (선택)
                "auto_add": bool     # filter용 자동 추가 (선택)
            }

        Returns:
            operation에 따른 결과
        """
        operation = data.get("operation", "check")

        if operation == "check":
            return self._check_duplicate(data)
        elif operation == "add":
            return self._add_to_db(data)
        elif operation == "filter":
            return self._filter_duplicates(data)
        elif operation == "stats":
            return self._get_stats()
        elif operation == "clear":
            return self._clear_category(data)
        else:
            return {"error": "잘못된 operation"}

    def _check_duplicate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """중복 체크"""
        item = data["item"]
        category = data.get("category", "default")
        use_hash = data.get("use_hash", False)

        if use_hash:
            item = self.generate_hash(item)

        db = self.load_db()
        items = db.get(category, [])

        return {
            "is_duplicate": item in items,
            "category": category,
            "operation": "check"
        }

    def _add_to_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """DB에 항목 추가"""
        item = data["item"]
        category = data.get("category", "default")
        cleanup = data.get("cleanup", True)
        use_hash = data.get("use_hash", False)

        if use_hash:
            item = self.generate_hash(item)

        db = self.load_db()

        if category not in db:
            db[category] = []

        if item in db[category]:
            return {"success": False, "already_exists": True, "operation": "add"}

        db[category].append(item)

        if cleanup and len(db[category]) > self.max_entries:
            db[category] = db[category][-self.max_entries:]

        success = self.save_db(db)

        return {
            "success": success,
            "category": category,
            "total_items": len(db[category]),
            "operation": "add"
        }

    def _filter_duplicates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """중복 필터링"""
        items = data["items"]
        category = data.get("category", "default")
        auto_add = data.get("auto_add", False)

        db = self.load_db()
        existing = set(db.get(category, []))

        filtered = [item for item in items if item not in existing]

        if auto_add:
            for item in filtered:
                self._add_to_db({
                    "item": item,
                    "category": category,
                    "cleanup": False
                })

        return {
            "filtered": filtered,
            "original_count": len(items),
            "filtered_count": len(filtered),
            "removed_count": len(items) - len(filtered),
            "operation": "filter"
        }

    def _get_stats(self) -> Dict[str, Any]:
        """DB 통계"""
        db = self.load_db()
        total_items = sum(len(items) for items in db.values())

        return {
            "total_categories": len(db),
            "total_items": total_items,
            "categories": {cat: len(items) for cat, items in db.items()},
            "db_path": str(self.db_path),
            "max_entries": self.max_entries,
            "operation": "stats"
        }

    def _clear_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """카테고리 삭제"""
        category = data.get("category")

        if category:
            db = self.load_db()
            if category in db:
                del db[category]
                return {"success": self.save_db(db), "operation": "clear"}
        else:
            try:
                if self.db_path.exists():
                    self.db_path.unlink()
                return {"success": True, "operation": "clear_all"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "operation": "clear"}

    def load_db(self) -> Dict[str, List[str]]:
        """DB 로드"""
        if not self.db_path.exists():
            return {}

        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_db(self, data: Dict[str, List[str]]) -> bool:
        """DB 저장"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def generate_hash(self, text: str) -> str:
        """텍스트 해시 생성"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
