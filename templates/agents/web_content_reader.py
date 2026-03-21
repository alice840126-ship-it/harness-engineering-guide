#!/usr/bin/env python3
"""
웹 콘텐츠 리더 에이전트

웹페이지 본문을 추출하는 재사용 가능한 에이전트
trafilatura를 사용하여 깨끗한 본문 텍스트 추출
"""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebContentReader:
    """웹 콘텐츠 리더 에이전트"""

    def __init__(self, timeout: int = 15, max_chars: int = 2000):
        """
        초기화

        Args:
            timeout: 요청 타임아웃 (초)
            max_chars: 최대 추출 길이
        """
        self.timeout = timeout
        self.max_chars = max_chars

        # trafilatura 임포트 (지연 로딩)
        try:
            import trafilatura
            self.trafilatura = trafilatura
        except ImportError:
            logger.error("trafilatura가 설치되지 않았습니다. pip install trafilatura")
            self.trafilatura = None

    def read_content(
        self,
        url: str,
        include_comments: bool = False,
        include_tables: bool = False
    ) -> Optional[str]:
        """
        단일 URL 본문 추출

        Args:
            url: 웹페이지 URL
            include_comments: 댓글 포함 여부
            include_tables: 표 포함 여부

        Returns:
            추출된 본문 텍스트 (실패 시 None)
        """
        if not self.trafilatura:
            logger.error("trafilatura 모듈을 사용할 수 없습니다")
            return None

        # URL 검증
        if not self._is_valid_url(url):
            logger.warning(f"유효하지 않은 URL: {url}")
            return None

        try:
            # 웹페이지 다운로드
            downloaded = self.trafilatura.fetch_url(url, timeout=self.timeout)

            if not downloaded:
                logger.warning(f"다운로드 실패: {url}")
                return None

            # 본문 추출
            content = self.trafilatura.extract(
                downloaded,
                include_comments=include_comments,
                include_tables=include_tables,
                no_fallback=False  # 실패 시 대체 방법 사용
            )

            if content:
                # 길이 제한
                if len(content) > self.max_chars:
                    content = content[:self.max_chars]

                logger.info(f"✅ 본문 추출 성공: {url} ({len(content)}자)")
                return content
            else:
                logger.warning(f"본문 추출 실패: {url}")
                return None

        except Exception as e:
            logger.error(f"❌ 본문 추출 오류 ({url}): {e}")
            return None

    def read_multiple_contents(
        self,
        urls: List[str],
        include_comments: bool = False,
        include_tables: bool = False,
        skip_errors: bool = True
    ) -> List[Dict[str, Optional[str]]]:
        """
        여러 URL 일괄 본문 추출

        Args:
            urls: 웹페이지 URL 리스트
            include_comments: 댓글 포함 여부
            include_tables: 표 포함 여부
            skip_errors: 실패 시 계속 진행 여부

        Returns:
            [{url, content, status}] 리스트
        """
        results = []

        for url in urls:
            content = self.read_content(url, include_comments, include_tables)

            status = "success" if content else "failed"

            results.append({
                "url": url,
                "content": content,
                "status": status
            })

            # 실패 시 중단 옵션
            if not skip_errors and not content:
                logger.error("❌ 일괄 처리 중단")
                break

        # 성공 개수 로깅
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"✅ 일괄 처리 완료: {success_count}/{len(urls)} 성공")

        return results

    def extract_main_content(self, html: str) -> Optional[str]:
        """
        HTML에서 본문만 추출 (이미 다운로드된 HTML)

        Args:
            html: HTML 문자열

        Returns:
            추출된 본문 텍스트
        """
        if not self.trafilatura:
            return None

        try:
            content = self.trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False
            )

            if content and len(content) > self.max_chars:
                content = content[:self.max_chars]

            return content

        except Exception as e:
            logger.error(f"❌ HTML 추출 오류: {e}")
            return None

    def _is_valid_url(self, url: str) -> bool:
        """
        URL 유효성 검사

        Args:
            url: 검사할 URL

        Returns:
            유효 여부
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def get_metadata(self, url: str) -> Optional[Dict[str, str]]:
        """
        웹페이지 메타데이터 추출

        Args:
            url: 웹페이지 URL

        Returns:
            메타데이터 딕셔너리 (title, author, date, etc.)
        """
        if not self.trafilatura:
            return None

        try:
            downloaded = self.trafilatura.fetch_url(url, timeout=self.timeout)

            if not downloaded:
                return None

            metadata = self.trafilatura.extract_metadata(downloaded)

            if metadata:
                return {
                    "title": metadata.title or "",
                    "author": metadata.author or "",
                    "date": metadata.date or "",
                    "url": url
                }

            return None

        except Exception as e:
            logger.error(f"❌ 메타데이터 추출 오류 ({url}): {e}")
            return None
