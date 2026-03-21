#!/usr/bin/env python3
"""
중복 필터 에이전트

URL/제목/ID 기반 중복 제거 시스템
JSON 기반 데이터베이스로 영구 저장
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import hashlib

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DuplicateFilter:
    """중복 필터 에이전트"""

    def __init__(self, db_path: Optional[Path] = None, max_entries: int = 100):
        """
        초기화

        Args:
            db_path: 데이터베이스 파일 경로 (기본: ~/.claude/duplicate_filter.json)
            max_entries: 최대 저장 개수 (오래된 항목 삭제)
        """
        self.db_path = db_path or Path.home() / ".claude" / "duplicate_filter.json"
        self.max_entries = max_entries

        # DB 폴더 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def load_db(self) -> Dict[str, List[str]]:
        """
        데이터베이스 로드

        Returns:
            {category: [items]} 딕셔너리
        """
        if not self.db_path.exists():
            return {}

        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ DB 로드 실패: {e}")
            return {}

    def save_db(self, data: Dict[str, List[str]]) -> bool:
        """
        데이터베이스 저장

        Args:
            data: 저장할 데이터

        Returns:
            성공 여부
        """
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"❌ DB 저장 실패: {e}")
            return False

    def is_duplicate(
        self,
        item: str,
        category: str = "default"
    ) -> bool:
        """
        중복 체크

        Args:
            item: 확인할 항목 (URL, 제목 등)
            category: 카테고리 (기본: default)

        Returns:
            중복 여부
        """
        db = self.load_db()
        items = db.get(category, [])

        return item in items

    def add_to_db(
        self,
        item: str,
        category: str = "default",
        cleanup: bool = True
    ) -> bool:
        """
        데이터베이스에 항목 추가

        Args:
            item: 추가할 항목
            category: 카테고리
            cleanup: 오래된 항목 정리 여부

        Returns:
            성공 여부
        """
        db = self.load_db()

        # 카테고리 초기화
        if category not in db:
            db[category] = []

        # 중복 체크
        if item in db[category]:
            logger.debug(f"이미 존재함: {item[:50]}...")
            return False

        # 추가
        db[category].append(item)

        # 정리 (오래된 항목 삭제)
        if cleanup and len(db[category]) > self.max_entries:
            db[category] = db[category][-self.max_entries:]
            logger.info(f"🧹 DB 정리: {category} ({len(db[category])}개 유지)")

        # 저장
        return self.save_db(db)

    def add_multiple_to_db(
        self,
        items: List[str],
        category: str = "default",
        cleanup: bool = True
    ) -> int:
        """
        여러 항목 일괄 추가

        Args:
            items: 추가할 항목 리스트
            category: 카테고리
            cleanup: 오래된 항목 정리 여부

        Returns:
            추가된 개수
        """
        added_count = 0

        for item in items:
            if self.add_to_db(item, category, cleanup=False):
                added_count += 1

        # 마지막에 한 번만 정리
        if cleanup:
            db = self.load_db()
            if category in db and len(db[category]) > self.max_entries:
                db[category] = db[category][-self.max_entries:]
                self.save_db(db)
                logger.info(f"🧹 DB 정리: {category}")

        return added_count

    def filter_duplicates(
        self,
        items: List[str],
        category: str = "default",
        auto_add: bool = False
    ) -> List[str]:
        """
        중복 필터링

        Args:
            items: 필터링할 항목 리스트
            category: 카테고리
            auto_add: 자동으로 DB에 추가 여부

        Returns:
            중복이 제거된 항목 리스트
        """
        db = self.load_db()
        existing = set(db.get(category, []))

        # 중복 필터링
        filtered = [item for item in items if item not in existing]

        logger.info(f"🔍 필터링: {len(items)}개 → {len(filtered)}개 (제거: {len(items) - len(filtered)}개)")

        # 자동 추가
        if auto_add:
            self.add_multiple_to_db(filtered, category)

        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """
        데이터베이스 통계

        Returns:
            통계 정보 딕셔너리
        """
        db = self.load_db()

        total_items = sum(len(items) for items in db.values())

        return {
            "total_categories": len(db),
            "total_items": total_items,
            "categories": {cat: len(items) for cat, items in db.items()},
            "db_path": str(self.db_path),
            "max_entries": self.max_entries
        }

    def clear_category(self, category: str) -> bool:
        """
        특정 카테고리 삭제

        Args:
            category: 삭제할 카테고리

        Returns:
            성공 여부
        """
        db = self.load_db()

        if category in db:
            del db[category]
            return self.save_db(db)

        return False

    def clear_all(self) -> bool:
        """
        전체 데이터베이스 초기화

        Returns:
            성공 여부
        """
        try:
            if self.db_path.exists():
                self.db_path.unlink()
                logger.info("🗑️ DB 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"❌ DB 초기화 실패: {e}")
            return False

    def generate_hash(self, text: str) -> str:
        """
        텍스트 해시 생성 (긴 텍스트 중복 체크용)

        Args:
            text: 해시 생성할 텍스트

        Returns:
            SHA256 해시값
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def is_duplicate_by_hash(
        self,
        text: str,
        category: str = "hash"
    ) -> bool:
        """
        해시 기반 중복 체크 (긴 텍스트용)

        Args:
            text: 확인할 텍스트
            category: 카테고리 (기본: hash)

        Returns:
            중복 여부
        """
        text_hash = self.generate_hash(text)
        return self.is_duplicate(text_hash, category)

    def add_text_by_hash(
        self,
        text: str,
        category: str = "hash"
    ) -> bool:
        """
        텍스트를 해시로 변환하여 추가 (긴 텍스트용)

        Args:
            text: 추가할 텍스트
            category: 카테고리

        Returns:
            성공 여부
        """
        text_hash = self.generate_hash(text)
        return self.add_to_db(text_hash, category)

    def export_backup(self, backup_path: Optional[Path] = None) -> bool:
        """
        데이터베이스 백업

        Args:
            backup_path: 백업 파일 경로 (기본: DB파일명.backup)

        Returns:
            성공 여부
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.parent / f"{self.db_path.stem}_{timestamp}.backup"

        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"💾 백업 완료: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 백업 실패: {e}")
            return False
