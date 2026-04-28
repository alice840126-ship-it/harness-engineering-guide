#!/usr/bin/env python3
"""
중복 필터 에이전트 단위 테스트
"""

import sys
import os
import tempfile
from pathlib import Path

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from duplicate_filter import DuplicateFilter


def test_is_duplicate():
    """중복 체크 테스트"""
    # 임시 DB 사용
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 첫 번째 항목 (중복 아님)
        item1 = "https://example.com/article1"
        is_dup1 = filter_agent.is_duplicate(item1)
        assert not is_dup1, "첫 번째 항목은 중복이 아님"

        # 추가
        filter_agent.add_to_db(item1)

        # 다시 체크 (중복)
        is_dup2 = filter_agent.is_duplicate(item1)
        assert is_dup2, "추가 후 중복 체크 실패"

        print("✅ test_is_duplicate: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_add_to_db():
    """DB 추가 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 항목 추가
        item = "https://example.com/test"
        success = filter_agent.add_to_db(item)

        assert success, "추가 실패"

        # 확인
        is_dup = filter_agent.is_duplicate(item)
        assert is_dup, "추가 후 중복 체크 실패"

        print("✅ test_add_to_db: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_add_multiple_to_db():
    """일괄 추가 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 여러 항목
        items = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

        added_count = filter_agent.add_multiple_to_db(items)

        assert added_count == 3, f"일괄 추가 실패: {added_count}/3"

        # 확인
        for item in items:
            assert filter_agent.is_duplicate(item), f"{item} 중복 체크 실패"

        print("✅ test_add_multiple_to_db: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_filter_duplicates():
    """중복 필터링 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 기존 항목 추가
        existing_items = ["https://example.com/1", "https://example.com/2"]
        filter_agent.add_multiple_to_db(existing_items)

        # 새 항목 + 중복 항목
        new_items = [
            "https://example.com/1",  # 중복
            "https://example.com/3",  # 새로운
            "https://example.com/2",  # 중복
            "https://example.com/4",  # 새로운
        ]

        filtered = filter_agent.filter_duplicates(new_items, auto_add=False)

        # 1, 2는 중복이라 제거되어야 함
        assert len(filtered) == 2, f"필터링 실패: {len(filtered)}개 (예상: 2개)"
        assert "https://example.com/3" in filtered, "항목 3 누락"
        assert "https://example.com/4" in filtered, "항목 4 누락"

        print("✅ test_filter_duplicates: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_categories():
    """카테고리별 분리 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 다른 카테고리에 같은 항목 추가
        item = "https://example.com/same"
        filter_agent.add_to_db(item, category="news")
        filter_agent.add_to_db(item, category="blog")

        # 카테고리별 체크
        assert filter_agent.is_duplicate(item, category="news"), "news 카테고리 체크 실패"
        assert filter_agent.is_duplicate(item, category="blog"), "blog 카테고리 체크 실패"

        # 다른 카테고리에서는 중복 아님
        assert not filter_agent.is_duplicate(item, category="other"), "다른 카테고리는 중복 아님"

        print("✅ test_categories: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_max_entries_cleanup():
    """최대 항목 제한 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db, max_entries=5)

        # 10개 항목 추가
        items = [f"https://example.com/{i}" for i in range(10)]
        filter_agent.add_multiple_to_db(items)

        # stats 확인
        stats = filter_agent.get_stats()
        category_items = stats["categories"].get("default", 0)

        assert category_items <= 5, f"최대 항목 초과: {category_items}개 (최대 5개)"

        print(f"✅ test_max_entries_cleanup: 테스트 통과 ({category_items}개 유지)")

    finally:
        temp_db.unlink(missing_ok=True)


def test_get_stats():
    """통계 정보 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db, max_entries=10)

        # 카테고리별 추가
        filter_agent.add_to_db("item1", category="news")
        filter_agent.add_to_db("item2", category="news")
        filter_agent.add_to_db("item3", category="blog")

        stats = filter_agent.get_stats()

        assert stats["total_categories"] == 2, "카테고리 수 불일치"
        assert stats["total_items"] == 3, "총 항목 수 불일치"
        assert stats["categories"]["news"] == 2, "news 카테고리 항목 수 불일치"
        assert stats["categories"]["blog"] == 1, "blog 카테고리 항목 수 불일치"
        assert stats["max_entries"] == 10, "최대 항목 수 불일치"

        print("✅ test_get_stats: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_clear_category():
    """카테고리 삭제 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 항목 추가
        filter_agent.add_to_db("item1", category="news")
        filter_agent.add_to_db("item2", category="blog")

        # news 카테고리 삭제
        success = filter_agent.clear_category("news")

        assert success, "삭제 실패"

        # 확인
        assert not filter_agent.is_duplicate("item1", category="news"), "news 항목 삭제 실패"
        assert filter_agent.is_duplicate("item2", category="blog"), "blog 항목 삭제됨 (안 됨)"

        print("✅ test_clear_category: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_clear_all():
    """전체 삭제 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 항목 추가
        filter_agent.add_to_db("item1", category="news")
        filter_agent.add_to_db("item2", category="blog")

        # 전체 삭제
        success = filter_agent.clear_all()

        assert success, "전체 삭제 실패"

        # DB 파일 삭제 확인
        assert not temp_db.exists(), "DB 파일 삭제됨"

        # 통계 확인
        stats = filter_agent.get_stats()
        assert stats["total_items"] == 0, "전체 항목 삭제됨"

        print("✅ test_clear_all: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def test_hash_based():
    """해시 기반 중복 체크 테스트"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_db = Path(f.name)

    try:
        filter_agent = DuplicateFilter(db_path=temp_db)

        # 긴 텍스트
        long_text = "이것은 매우 긴 텍스트입니다. " * 100

        # 해시 기반 추가
        filter_agent.add_text_by_hash(long_text, category="hash")

        # 중복 체크
        is_dup = filter_agent.is_duplicate_by_hash(long_text, category="hash")
        assert is_dup, "해시 기반 중복 체크 실패"

        # 다른 텍스트는 중복 아님
        other_text = "다른 텍스트입니다. " * 100
        is_not_dup = not filter_agent.is_duplicate_by_hash(other_text, category="hash")
        assert is_not_dup, "다른 텍스트는 중복이 아님"

        print("✅ test_hash_based: 테스트 통과")

    finally:
        temp_db.unlink(missing_ok=True)


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 중복 필터 에이전트 테스트 시작")
    print("=" * 50)

    test_is_duplicate()
    test_add_to_db()
    test_add_multiple_to_db()
    test_filter_duplicates()
    test_categories()
    test_max_entries_cleanup()
    test_get_stats()
    test_clear_category()
    test_clear_all()
    test_hash_based()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
