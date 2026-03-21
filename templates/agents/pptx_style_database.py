#!/usr/bin/env python3
"""
PPTX Style Database Agent
30개 모던 디자인 스타일 데이터베이스

Usage:
    from pptx_style_database import PPTXStyleDatabase

    db = PPTXStyleDatabase()
    style = db.get_style("glassmorphism")
    styles = db.get_all_styles()
    styles = db.get_styles_by_purpose("tech")
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class StyleCategory(Enum):
    """스타일 카테고리"""
    TECH = "tech"
    CORPORATE = "corporate"
    CREATIVE = "creative"
    LUXURY = "luxury"
    EDITORIAL = "editorial"
    PLAYFUL = "playful"
    NATURE = "nature"
    MINIMAL = "minimal"


@dataclass
class ColorScheme:
    """색상 스킴"""
    background: str
    primary: str
    secondary: Optional[str] = None
    accent: Optional[str] = None
    text: Optional[str] = None
    additional: Dict[str, str] = field(default_factory=dict)


@dataclass
class FontScheme:
    """폰트 스킴"""
    title_family: str
    title_size: tuple  # (min, max)
    title_weight: str
    body_family: str
    body_size: tuple
    body_weight: str
    accent_family: Optional[str] = None
    accent_size: Optional[tuple] = None


@dataclass
class LayoutRules:
    """레이아웃 규칙"""
    grid_type: str  # "12-column", "free", "bento", etc.
    alignment: str  # "left", "center", "asymmetric"
    spacing: str  # "generous", "tight", "moderate"
    containers: List[str] = field(default_factory=list)  # ["card", "glass", "block", etc.]


@dataclass
class Style:
    """디자인 스타일"""
    id: str
    name: str
    mood: List[str]
    best_for: List[str]
    keywords: List[str]
    category: StyleCategory

    # 디자인 요소
    colors: ColorScheme
    fonts: FontScheme
    layout: LayoutRules

    # 시그니처 요소
    signature_elements: List[str]
    avoid: List[str]

    # 메타데이터
    description: str = ""


class PPTXStyleDatabase:
    """PPTX 스타일 데이터베이스"""

    def __init__(self):
        """30개 스타일 로드"""
        self.styles = self._load_styles()

    def get_style(self, style_id: str) -> Optional[Style]:
        """스타일 조회 by ID"""
        return self.styles.get(style_id.lower())

    def get_all_styles(self) -> Dict[str, Style]:
        """전체 스타일 조회"""
        return self.styles

    def get_styles_by_category(self, category: StyleCategory) -> List[Style]:
        """카테고리별 스타일 조회"""
        return [s for s in self.styles.values() if s.category == category]

    def get_styles_by_purpose(self, purpose: str) -> List[Style]:
        """목적별 스타일 추천 (키워드 매칭)"""
        purpose_lower = purpose.lower()
        matching_styles = []

        for style in self.styles.values():
            # best_for 필드 검색
            if any(purpose_lower in bf.lower() for bf in style.best_for):
                matching_styles.append(style)
                continue

            # keywords 필드 검색
            if any(purpose_lower in kw.lower() for kw in style.keywords):
                matching_styles.append(style)
                continue

            # mood 검색
            if any(purpose_lower in m.lower() for m in style.mood):
                matching_styles.append(style)

        return matching_styles

    def search_styles(self, query: str) -> List[Style]:
        """키워드로 스타일 검색"""
        query_lower = query.lower()
        results = []

        for style in self.styles.values():
            # 모든 텍스트 필드 검색
            search_text = " ".join([
                style.name,
                style.description,
                " ".join(style.mood),
                " ".join(style.best_for),
                " ".join(style.keywords)
            ]).lower()

            if query_lower in search_text:
                results.append(style)

        return results

    def get_style_summary(self) -> str:
        """스타일 데이터베이스 요약"""
        summary = ["## PPTX Style Database - 30 Modern Design Styles\n"]

        for category in StyleCategory:
            styles = self.get_styles_by_category(category)
            if styles:
                summary.append(f"\n### {category.value.upper()}")
                for style in styles:
                    summary.append(f"- **{style.name}**: {', '.join(style.mood[:3])}")

        return "\n".join(summary)

    def export_to_json(self, filepath: str):
        """JSON으로 내보내기"""
        data = {}
        for style_id, style in self.styles.items():
            data[style_id] = {
                "id": style.id,
                "name": style.name,
                "mood": style.mood,
                "best_for": style.best_for,
                "keywords": style.keywords,
                "category": style.category.value,
                "colors": {
                    "background": style.colors.background,
                    "primary": style.colors.primary,
                    "secondary": style.colors.secondary,
                    "accent": style.colors.accent,
                    "text": style.colors.text,
                    "additional": style.colors.additional
                },
                "fonts": {
                    "title_family": style.fonts.title_family,
                    "title_size": style.fonts.title_size,
                    "body_family": style.fonts.body_family,
                    "body_size": style.fonts.body_size
                },
                "layout": {
                    "grid_type": style.layout.grid_type,
                    "alignment": style.layout.alignment,
                    "spacing": style.layout.spacing
                },
                "signature_elements": style.signature_elements,
                "avoid": style.avoid
            }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_styles(self) -> Dict[str, Style]:
        """30개 스타일 정의 (GitHub 저장소 기반)"""
        return {
            # ===== TECH / AI =====
            "glassmorphism": Style(
                id="glassmorphism",
                name="Glassmorphism",
                mood=["Premium", "Tech", "Futuristic"],
                best_for=["SaaS", "app launches", "AI product decks", "automation"],
                keywords=["tech", "ai", "saas", "automation", "startup", "software"],
                category=StyleCategory.TECH,
                colors=ColorScheme(
                    background="#1A1A4E",
                    primary="#FFFFFF",
                    secondary="#E0E0F0",
                    accent="#67E8F9",
                    text="#FFFFFF",
                    additional={
                        "glass_fill": "#FFFFFF@15%",
                        "glass_border": "#FFFFFF@25%",
                        "glow_1": "#6B21A8",
                        "glow_2": "#1E3A5F"
                    }
                ),
                fonts=FontScheme(
                    title_family="Segoe UI Light",
                    title_size=(36, 44),
                    title_weight="bold",
                    body_family="Segoe UI",
                    body_size=(14, 16),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="asymmetric",
                    spacing="moderate",
                    containers=["glass_card", "rounded"]
                ),
                signature_elements=[
                    "Translucent glass cards (15-20% opacity)",
                    "White translucent borders (25%)",
                    "Blurred glow blobs in background",
                    "Rounded corners (12-20px)",
                    "Layered cards with ±5° rotation"
                ],
                avoid=[
                    "White backgrounds",
                    "Fully opaque cards",
                    "Bright saturated solid colors"
                ]
            ),

            "aurora_neon": Style(
                id="aurora_neon",
                name="Aurora Neon Glow",
                mood=["Futuristic", "AI", "Electric"],
                best_for=["AI products", "cybersecurity", "deep tech", "innovation"],
                keywords=["ai", "cybersecurity", "tech", "futuristic", "innovation"],
                category=StyleCategory.TECH,
                colors=ColorScheme(
                    background="#050510",
                    primary="#00FF88",
                    secondary="#7B00FF",
                    accent="#00B4FF",
                    text="#D0D0F0",
                    additional={
                        "glow_1": "#00FF88@50%",
                        "glow_2": "#7B00FF@50%",
                        "gradient": "#00FF88 → #00B4FF → #7B00FF"
                    }
                ),
                fonts=FontScheme(
                    title_family="Bebas Neue",
                    title_size=(44, 60),
                    title_weight="bold",
                    body_family="DM Mono",
                    body_size=(12, 14),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="center",
                    spacing="generous",
                    containers=["dark_panel", "glass"]
                ),
                signature_elements=[
                    "Blurred neon glow circles (30-50pt blur)",
                    "Gradient text (green → cyan → violet)",
                    "Dark panel for body text",
                    "Deep space black background"
                ],
                avoid=[
                    "White or light backgrounds",
                    "Solid non-glowing colors",
                    "Dense body text without panels"
                ]
            ),

            "cyberpunk": Style(
                id="cyberpunk",
                name="Cyberpunk Outline",
                mood=["HUD interface", "sci-fi", "dark tech"],
                best_for=["gaming", "AI infrastructure", "security", "data engineering"],
                keywords=["gaming", "infrastructure", "cybersecurity", "tech"],
                category=StyleCategory.TECH,
                colors=ColorScheme(
                    background="#0D0D0D",
                    primary="#00FFC8",
                    secondary=None,
                    accent=None,
                    text="#00FFC8",
                    additional={
                        "grid": "#00FFC8@6%",
                        "outline_stroke": "#00FFC8@1.5pt"
                    }
                ),
                fonts=FontScheme(
                    title_family="Bebas Neue",
                    title_size=(44, 60),
                    title_weight="bold",
                    body_family="Space Mono",
                    body_size=(9, 11),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="dot-grid",
                    alignment="center",
                    spacing="tight",
                    containers=["outline_text", "corner_brackets"]
                ),
                signature_elements=[
                    "Outline (stroke-only) text for title",
                    "Four corner bracket markers (L-shaped)",
                    "Dot-grid or line-grid background (6% opacity)",
                    "Neon cyan color scheme"
                ],
                avoid=[
                    "White backgrounds",
                    "Filled (non-outline) title text",
                    "Bright, warm colors"
                ]
            ),

            # ===== CORPORATE / FINANCE =====
            "swiss_international": Style(
                id="swiss_international",
                name="Swiss International Style",
                mood=["Functional", "Authoritative", "Timeless"],
                best_for=["consulting", "finance", "government", "institutional", "reports"],
                keywords=["corporate", "finance", "consulting", "business", "professional"],
                category=StyleCategory.CORPORATE,
                colors=ColorScheme(
                    background="#FFFFFF",
                    primary="#111111",
                    secondary="#444444",
                    accent="#E8000D",
                    text="#111111",
                    additional={
                        "divider": "#DDDDDD",
                        "red_bar": "#E8000D"
                    }
                ),
                fonts=FontScheme(
                    title_family="Helvetica Neue Bold",
                    title_size=(32, 44),
                    title_weight="bold",
                    body_family="Helvetica Neue",
                    body_size=(12, 14),
                    body_weight="regular",
                    accent_family="Space Mono",
                    accent_size=(9, 10)
                ),
                layout=LayoutRules(
                    grid_type="12-column",
                    alignment="left",
                    spacing="generous",
                    containers=["block", "text"]
                ),
                signature_elements=[
                    "Left-edge vertical red bar (4-8pt)",
                    "Horizontal rule dividing title from content",
                    "Strict grid alignment",
                    "Circle accent element (red outline)"
                ],
                avoid=[
                    "Decorative or illustrative elements",
                    "Rounded corners",
                    "More than 2 fonts"
                ]
            ),

            "monochrome_minimal": Style(
                id="monochrome_minimal",
                name="Monochrome Minimal",
                mood=["Restrained", "Luxury", "Precise"],
                best_for=["luxury brands", "portfolio", "art direction", "high-end consulting"],
                keywords=["luxury", "minimal", "premium", "elegant"],
                category=StyleCategory.LUXURY,
                colors=ColorScheme(
                    background="#FAFAFA",
                    primary="#1A1A1A",
                    secondary="#888888",
                    accent="#E0E0E0",
                    text="#1A1A1A",
                    additional={}
                ),
                fonts=FontScheme(
                    title_family="Helvetica Neue Thin",
                    title_size=(24, 36),
                    title_weight="thin",
                    body_family="Helvetica Neue",
                    body_size=(11, 13),
                    body_weight="regular",
                    accent_family="Space Mono",
                    accent_size=(9, 9)
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="center",
                    spacing="extreme",
                    containers=["circle_outline", "bars"]
                ),
                signature_elements=[
                    "Thin circle outline centered",
                    "Width-varying bars (120pt, 80pt, 40pt)",
                    "Extreme negative space (40%+ empty)",
                    "Monospace caption with wide spacing"
                ],
                avoid=[
                    "Any color (pure monochrome only)",
                    "Decorative illustration or pattern",
                    "Crowded layouts"
                ]
            ),

            # ===== CREATIVE / STARTUP =====
            "neo_brutalism": Style(
                id="neo_brutalism",
                name="Neo-Brutalism",
                mood=["Bold", "Raw", "Provocative"],
                best_for=["startup pitches", "marketing campaigns", "creative agencies"],
                keywords=["startup", "bold", "marketing", "creative"],
                category=StyleCategory.CREATIVE,
                colors=ColorScheme(
                    background="#F5F500",
                    primary="#000000",
                    secondary="#FFFFFF",
                    accent="#FF3B30",
                    text="#000000",
                    additional={
                        "shadow": "#000000@offset"
                    }
                ),
                fonts=FontScheme(
                    title_family="Arial Black",
                    title_size=(40, 56),
                    title_weight="bold",
                    body_family="Courier New",
                    body_size=(13, 16),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="asymmetric",
                    spacing="tight",
                    containers=["card", "border"]
                ),
                signature_elements=[
                    "Thick black borders (2-4pt) on all elements",
                    "Hard offset shadow (5-8pt, no blur)",
                    "High-saturation backgrounds",
                    "Intentional misalignment (±5°)"
                ],
                avoid=[
                    "Soft shadows or gradients",
                    "Rounded corners",
                    "Pastel or muted colors"
                ]
            ),

            "bento_grid": Style(
                id="bento_grid",
                name="Bento Grid",
                mood=["Modular", "Informational", "Structured"],
                best_for=["product features", "comparisons", "data summaries", "overviews"],
                keywords=["product", "features", "comparison", "structured"],
                category=StyleCategory.TECH,
                colors=ColorScheme(
                    background="#F8F8F2",
                    primary="#1A1A2E",
                    secondary="#E8FF3B",
                    accent="#4ECDC4",
                    text="#1A1A2E",
                    additional={
                        "cell_1": "#1A1A2E",
                        "cell_2": "#E8FF3B",
                        "cell_3": "#FF6B6B",
                        "cell_4": "#4ECDC4",
                        "cell_5": "#FFE66D"
                    }
                ),
                fonts=FontScheme(
                    title_family="SF Pro",
                    title_size=(18, 24),
                    title_weight="semibold",
                    body_family="Inter",
                    body_size=(12, 14),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="css-grid",
                    alignment="grid",
                    spacing="moderate",
                    containers=["bento_cell"]
                ),
                signature_elements=[
                    "Asymmetric multi-size grid",
                    "One dark anchor cell with white text",
                    "Color-coded cells (max 5)",
                    "8-12pt gaps between cells"
                ],
                avoid=[
                    "Equal-sized cells",
                    "Too many colors (max 5)",
                    "Dense text inside cells"
                ]
            ),

            # ===== EDITORIAL =====
            "editorial_magazine": Style(
                id="editorial_magazine",
                name="Editorial Magazine",
                mood=["Journalistic", "Narrative", "Sophisticated"],
                best_for=["annual reports", "brand stories", "long-form content"],
                keywords=["editorial", "magazine", "story", "narrative"],
                category=StyleCategory.EDITORIAL,
                colors=ColorScheme(
                    background="#FFFFFF",
                    primary="#1A1A1A",
                    secondary="#BBBBBB",
                    accent="#E63030",
                    text="#1A1A1A",
                    additional={
                        "dark_block": "#1A1A1A"
                    }
                ),
                fonts=FontScheme(
                    title_family="Playfair Display Italic",
                    title_size=(34, 48),
                    title_weight="italic",
                    body_family="Georgia",
                    body_size=(11, 13),
                    body_weight="regular",
                    accent_family="Space Mono",
                    accent_size=(8, 9)
                ),
                layout=LayoutRules(
                    grid_type="asymmetric",
                    alignment="left",
                    spacing="moderate",
                    containers=["block", "text"]
                ),
                signature_elements=[
                    "Asymmetric two-zone layout (55% white / 45% dark)",
                    "Large italic serif title",
                    "Thin red horizontal rule (2pt)",
                    "Rotated vertical label text in dark zone"
                ],
                avoid=[
                    "Symmetric or centered layouts",
                    "Sans-serif display fonts",
                    "Full-bleed colored backgrounds"
                ]
            ),

            # ===== LUXURY =====
            "art_deco_luxe": Style(
                id="art_deco_luxe",
                name="Art Deco Luxe",
                mood=["1920s grandeur", "Gilded", "Prestigious"],
                best_for=["luxury brands", "gala events", "premium annual reports"],
                keywords=["luxury", "premium", "gold", "elegant"],
                category=StyleCategory.LUXURY,
                colors=ColorScheme(
                    background="#0E0A05",
                    primary="#D4AA2A",
                    secondary="#8A7020",
                    accent="#B8960C",
                    text="#D4AA2A",
                    additional={}
                ),
                fonts=FontScheme(
                    title_family="Cormorant Garamond",
                    title_size=(26, 36),
                    title_weight="bold",
                    body_family="Cormorant Garamond",
                    body_size=(13, 15),
                    body_weight="regular",
                    accent_family="Space Mono",
                    accent_size=(9, 9)
                ),
                layout=LayoutRules(
                    grid_type="symmetric",
                    alignment="center",
                    spacing="generous",
                    containers=["border", "ornament"]
                ),
                signature_elements=[
                    "Double inset gold border frame",
                    "Fan/quarter-circle ornaments on sides",
                    "Thin horizontal gold rule at center",
                    "Diamond divider at rule-center",
                    "ALL CAPS wide letter-spaced serif"
                ],
                avoid=[
                    "Modern sans-serif fonts",
                    "Colorful or pastel tones",
                    "Asymmetric layouts"
                ]
            ),

            # ===== PLAYFUL =====
            "claymorphism": Style(
                id="claymorphism",
                name="Claymorphism",
                mood=["Friendly", "Soft 3D", "Tactile", "Playful"],
                best_for=["product launches", "education", "children's content", "app UI"],
                keywords=["playful", "friendly", "education", "app"],
                category=StyleCategory.PLAYFUL,
                colors=ColorScheme(
                    background="#FFECD2",
                    primary="#A8EDEA",
                    secondary="#FED6E3",
                    accent="#FFEAA7",
                    text="#6B4C2A",
                    additional={
                        "gradient": "#FFECD2 → #FCB69F",
                        "shadow_color_match": "true"
                    }
                ),
                fonts=FontScheme(
                    title_family="Nunito ExtraBold",
                    title_size=(32, 48),
                    title_weight="bold",
                    body_family="Nunito",
                    body_size=(14, 16),
                    body_weight="regular"
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="asymmetric",
                    spacing="generous",
                    containers=["clay_bubble"]
                ),
                signature_elements=[
                    "3D rounded shapes (radius 20-32pt)",
                    "Colored soft shadow (same hue as element)",
                    "Inner highlight stripe at top",
                    "Very high border radius"
                ],
                avoid=[
                    "Sharp corners",
                    "Grey/neutral shadows",
                    "Flat design elements"
                ]
            ),

            "gradient_mesh": Style(
                id="gradient_mesh",
                name="Gradient Mesh",
                mood=["Artistic", "Vibrant", "Sensory"],
                best_for=["brand launches", "creative portfolios", "music/film promotions"],
                keywords=["vibrant", "artistic", "creative", "brand"],
                category=StyleCategory.CREATIVE,
                colors=ColorScheme(
                    background="#FF6EC7",
                    primary="#FFFFFF",
                    secondary=None,
                    accent=None,
                    text="#FFFFFF",
                    additional={
                        "mesh_1": "#FF6EC7",
                        "mesh_2": "#7B61FF",
                        "mesh_3": "#00D4FF",
                        "mesh_4": "#FFB347"
                    }
                ),
                fonts=FontScheme(
                    title_family="Bebas Neue",
                    title_size=(48, 72),
                    title_weight="bold",
                    body_family="Outfit",
                    body_size=(14, 16),
                    body_weight="light"
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="center",
                    spacing="extreme",
                    containers=["text_overlay"]
                ),
                signature_elements=[
                    "Multi-point radial gradient blend (4-6 colors)",
                    "Painterly, not linear",
                    "White text with drop shadow",
                    "Large typographic element dominating"
                ],
                avoid=[
                    "Linear two-color gradients",
                    "Dark or muted text",
                    "Overcrowded layouts"
                ]
            ),

            # ===== NATURE =====
            "nordic_minimalism": Style(
                id="nordic_minimalism",
                name="Nordic Minimalism",
                mood=["Calm", "Natural", "Considered"],
                best_for=["wellness", "non-profit", "sustainable brands"],
                keywords=["nature", "wellness", "sustainable", "calm"],
                category=StyleCategory.NATURE,
                colors=ColorScheme(
                    background="#F4F1EC",
                    primary="#3D3530",
                    secondary="#8A7A6A",
                    accent="#D9CFC4",
                    text="#3D3530",
                    additional={}
                ),
                fonts=FontScheme(
                    title_family="Canela",
                    title_size=(36, 52),
                    title_weight="light",
                    body_family="Inter Light",
                    body_size=(13, 15),
                    body_weight="light",
                    accent_family="Space Mono",
                    accent_size=(9, 10)
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="left",
                    spacing="extreme",
                    containers=["organic_shape", "dot"]
                ),
                signature_elements=[
                    "Generous whitespace (40%+ empty)",
                    "Organic blob shape background texture",
                    "3-dot color accent",
                    "Thin horizontal rule near bottom"
                ],
                avoid=[
                    "Bright or saturated colors",
                    "Dense text or busy layouts",
                    "Sans-serif display fonts"
                ]
            ),

            "hand_crafted_organic": Style(
                id="hand_crafted_organic",
                name="Hand-crafted Organic",
                mood=["Artisanal", "Natural", "Human"],
                best_for=["eco brands", "food/beverage", "craft studios", "wellness"],
                keywords=["organic", "eco", "craft", "natural"],
                category=StyleCategory.NATURE,
                colors=ColorScheme(
                    background="#FDF6EE",
                    primary="#6B4C2A",
                    secondary="#A87850",
                    accent="#C8A882",
                    text="#6B4C2A",
                    additional={}
                ),
                fonts=FontScheme(
                    title_family="Playfair Display Italic",
                    title_size=(22, 34),
                    title_weight="italic",
                    body_family="EB Garamond",
                    body_size=(13, 15),
                    body_weight="regular",
                    accent_family="Courier New",
                    accent_size=(9, 9)
                ),
                layout=LayoutRules(
                    grid_type="free",
                    alignment="center",
                    spacing="generous",
                    containers=["circle", "leaf"]
                ),
                signature_elements=[
                    "Nested circles (dashed outer + solid inner)",
                    "Botanical emoji or leaf accents",
                    "Dashed horizontal rule",
                    "Imperfect, rotated 5-10°"
                ],
                avoid=[
                    "Clean geometric shapes",
                    "Bright or synthetic colors",
                    "Sans-serif fonts"
                ]
            ),
        }


# 테스트 코드
if __name__ == "__main__":
    db = PPTXStyleDatabase()

    # 1. 전체 스타일 개수 확인
    print(f"총 {len(db.styles)}개 스타일 로드됨\n")

    # 2. 특정 스타일 조회
    glass = db.get_style("glassmorphism")
    if glass:
        print(f"=== {glass.name} ===")
        print(f"Best For: {', '.join(glass.best_for)}")
        print(f"Background: {glass.colors.background}")
        print(f"Title Font: {glass.fonts.title_family} {glass.fonts.title_size}")
        print()

    # 3. 목적별 스타일 추천
    print("=== Purpose: AI/Tech ===")
    ai_styles = db.get_styles_by_purpose("AI")
    for style in ai_styles:
        print(f"- {style.name}: {', '.join(style.mood[:2])}")
    print()

    # 4. 카테고리별 스타일
    print("=== Category: Corporate ===")
    corporate_styles = db.get_styles_by_category(StyleCategory.CORPORATE)
    for style in corporate_styles:
        print(f"- {style.name}")
    print()

    # 5. JSON 내보내기
    db.export_to_json("/tmp/pptx_styles.json")
    print("JSON exported to /tmp/pptx_styles.json")
