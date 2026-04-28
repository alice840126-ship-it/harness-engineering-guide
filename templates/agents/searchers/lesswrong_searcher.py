#!/usr/bin/env python3
"""LessWrong 검색 - GraphQL API (인증 없음, 멘탈모델/합리주의 커뮤니티)"""
import requests

GRAPHQL_URL = "https://www.lesswrong.com/graphql"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}


def _to_gql(d: dict) -> str:
    """Python dict → GraphQL 객체 리터럴 (키 따옴표 없음)"""
    parts = []
    for k, v in d.items():
        if isinstance(v, str):
            parts.append(f'{k}:"{v}"')
        elif isinstance(v, bool):
            parts.append(f'{k}:{str(v).lower()}')
        else:
            parts.append(f'{k}:{v}')
    return "{" + ",".join(parts) + "}"


def _fetch(terms: dict) -> list:
    gql_terms = _to_gql(terms)
    query = f"{{posts(input:{{terms:{gql_terms}}}){{results{{title pageUrl baseScore}}}}}}"
    try:
        r = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        posts = r.json().get("data", {}).get("posts", {}).get("results", [])
        return [
            {
                "title": p.get("title", ""),
                "url": p.get("pageUrl", ""),
                "description": (p.get("excerpt") or "")[:200],
                "score": p.get("baseScore", 0),
                "source": "lesswrong",
            }
            for p in posts if p.get("title")
        ]
    except Exception as e:
        print(f"[lesswrong_searcher] 실패: {e}")
        return []


def search(query: str, limit: int = 5) -> list:
    return _fetch({"limit": limit, "view": "new", "search": query})


def get_top(limit: int = 5) -> list:
    return _fetch({"limit": limit, "view": "new"})
