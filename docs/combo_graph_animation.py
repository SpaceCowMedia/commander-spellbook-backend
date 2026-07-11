"""
Manim animation script for explaining the combo graph algorithm in
backend/spellbook/variants/combo_graph.py.

Design goals:
- 3blue1brown-inspired visual style (clean geometry + moving labels)
- Low-formula, programmer-friendly narrative
- Down phase first, then up phase
- Abstract card view by default, easy manual swap to real cards
- Optional Scryfall image fetching with graceful fallback

Quick start (Windows, from repository root):
1) docs/.venv-manim/Scripts/python.exe -m manim -qh docs/combo_graph_animation.py IntroAndRoadmap
2) docs/.venv-manim/Scripts/python.exe -m manim -qh -a docs/combo_graph_animation.py

Manual customization entry points:
- CARD_MODE: "abstract" or "real"
- CARD_SPECS: edit labels and scryfall_query values
- GRAPH_DEFINITION: edit graph used in scenes
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap

import numpy as np
import requests
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter, ImageFont

from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    Arrow,
    BLUE_D,
    Circle,
    Create,
    Ellipse,
    FadeIn,
    FadeOut,
    GREEN,
    GREEN_D,
    Group,
    GREY_A,
    GREY_B,
    GREY_C,
    LaggedStart,
    Line,
    ORANGE,
    RED,
    RoundedRectangle,
    Scene,
    Square,
    SurroundingRectangle,
    Text,
    Transform,
    VGroup,
    WHITE,
    Write,
    YELLOW,
)


# ============================================================================
# Configurations and asset utilities
# ============================================================================

DOCS_DIR = Path(__file__).resolve().parent
ASSETS_DIR = DOCS_DIR / "animation_assets"
RAW_DIR = ASSETS_DIR / "raw"
BUILT_DIR = ASSETS_DIR / "built"

# "abstract" => blueprint-like card with real Scryfall art crop in frame
# "real" => full card image from Scryfall (normal image)
CARD_MODE = "abstract"

# Keep this True if you want first render to fetch remote assets.
# If False, script only uses local files and generated placeholders.
ALLOW_SCRYFALL_DOWNLOAD = True


@dataclass(frozen=True)
class CardSpec:
    key: str
    display_name: str
    role: str
    scryfall_query: str
    # Set this to a local path if you want to force a specific image.
    manual_image: str | None = None


CARD_SPECS: dict[str, CardSpec] = {
    "A": CardSpec("A", "Card A", "Engine piece", "Isochron Scepter"),
    "B": CardSpec("B", "Card B", "Engine piece", "Dramatic Reversal"),
    "C": CardSpec("C", "Card C", "Payoff bridge", "Blue Sun's Zenith"),
    "D": CardSpec("D", "Card D", "Primary finisher", "Thassa's Oracle"),
    "E": CardSpec("E", "Card E", "Alternate finisher", "Aetherflux Reservoir"),
    "X": CardSpec("X", "Card X", "Auxiliary source", "Sol Ring"),
    "Y": CardSpec("Y", "Card Y", "Auxiliary source", "Basalt Monolith"),
}


GRAPH_DEFINITION = {
    "combos": {
        "C1": {
            "label": "Mana Engine",
            "needs_cards": ["A", "B"],
            "needs_features": [],
            "produces": ["Infinite Mana"],
        },
        "C5": {
            "label": "Alt Mana Engine",
            "needs_cards": ["X", "Y"],
            "needs_features": [],
            "produces": ["Infinite Mana"],
        },
        "C2": {
            "label": "Convert Mana To Draw",
            "needs_cards": ["C"],
            "needs_features": ["Infinite Mana"],
            "produces": ["Draw Deck"],
        },
        "C3": {
            "label": "Draw To Win",
            "needs_cards": ["D"],
            "needs_features": ["Draw Deck"],
            "produces": ["Win"],
        },
        "C4": {
            "label": "Mana To Win",
            "needs_cards": ["E"],
            "needs_features": ["Infinite Mana"],
            "produces": ["Win"],
        },
    }
}


def _ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    BUILT_DIR.mkdir(parents=True, exist_ok=True)


def _slug(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s)


def _download_scryfall_json(query: str) -> dict | None:
    if not ALLOW_SCRYFALL_DOWNLOAD:
        return None
    try:
        url = "https://api.scryfall.com/cards/named"
        response = requests.get(url, params={"exact": query}, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _download_image(url: str, destination: Path) -> bool:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        destination.write_bytes(response.content)
        return True
    except Exception:
        return False


def _placeholder_image(path: Path, title: str, subtitle: str, size: tuple[int, int]) -> None:
    width, height = size
    img = PILImage.new("RGB", (width, height), color=(28, 31, 40))
    draw = ImageDraw.Draw(img)

    # Soft gradient-ish bars
    for i in range(0, height, 8):
        c = 30 + (i * 70 // max(height, 1))
        draw.rectangle([(0, i), (width, min(height, i + 8))], fill=(c // 2, c, min(255, c + 30)))

    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=24, outline=(245, 240, 225), width=5)
    draw.rounded_rectangle((40, 90, width - 40, height - 110), radius=16, outline=(240, 210, 170), width=3)

    try:
        font_title = ImageFont.truetype("arial.ttf", 34)
        font_sub = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.text((48, 32), title, fill=(250, 248, 240), font=font_title)
    draw.text((48, height - 84), subtitle, fill=(240, 225, 190), font=font_sub)
    img.save(path)


def _build_abstract_card(spec: CardSpec, art_source_path: Path, destination: Path) -> None:
    card_w, card_h = 744, 1039
    card = PILImage.new("RGB", (card_w, card_h), color=(240, 234, 220))

    # Frame and art region proportions roughly inspired by MTG cards.
    art_x0, art_y0, art_x1, art_y1 = 52, 138, card_w - 52, 620

    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((16, 16, card_w - 16, card_h - 16), radius=28, outline=(64, 52, 43), width=6)
    draw.rounded_rectangle((38, 78, card_w - 38, 120), radius=10, fill=(250, 247, 238), outline=(84, 70, 58), width=2)
    draw.rounded_rectangle((38, 646, card_w - 38, card_h - 90), radius=12, fill=(252, 249, 242), outline=(95, 80, 65), width=2)

    title = f"{spec.display_name}"
    type_line = f"Prototype - {spec.role}"

    try:
        font_title = ImageFont.truetype("arial.ttf", 34)
        font_type = ImageFont.truetype("arial.ttf", 26)
        font_body = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_type = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.text((56, 83), title, fill=(33, 28, 23), font=font_title)
    draw.text((56, 650), type_line, fill=(48, 38, 31), font=font_type)

    if art_source_path.exists():
        art = PILImage.open(art_source_path).convert("RGB")
    else:
        art = PILImage.new("RGB", (672, 482), color=(64, 80, 96))

    art = art.resize((art_x1 - art_x0, art_y1 - art_y0))
    # Slight vignette for a cleaner look
    overlay = PILImage.new("L", art.size, 0)
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle((0, 0, art.width, art.height), fill=175)
    overlay = overlay.filter(ImageFilter.GaussianBlur(20))
    art = PILImage.composite(art, PILImage.new("RGB", art.size, color=(30, 30, 36)), overlay)

    card.paste(art, (art_x0, art_y0))
    draw.rounded_rectangle((art_x0, art_y0, art_x1, art_y1), radius=12, outline=(84, 70, 58), width=3)

    body_text = textwrap.fill(
        f"This is an abstract stand-in for {spec.display_name}."
        f" Replace card specs to switch to real-card storytelling.",
        width=44,
    )
    draw.text((56, 708), body_text, fill=(35, 32, 28), font=font_body)

    footer = "Combo Graph Animation Blueprint"
    draw.text((56, 968), footer, fill=(70, 62, 58), font=font_body)

    card.save(destination)


def _ensure_card_asset(spec: CardSpec, mode: str) -> Path:
    _ensure_dirs()

    if spec.manual_image:
        manual_path = Path(spec.manual_image)
        if manual_path.exists():
            return manual_path

    base_name = _slug(spec.key + "_" + spec.scryfall_query)
    raw_art = RAW_DIR / f"{base_name}_art.jpg"
    raw_full = RAW_DIR / f"{base_name}_full.jpg"
    built_abstract = BUILT_DIR / f"{base_name}_abstract.png"

    if mode == "real":
        if raw_full.exists():
            return raw_full
    else:
        if built_abstract.exists():
            return built_abstract

    card_json = _download_scryfall_json(spec.scryfall_query)

    if card_json:
        image_uris = card_json.get("image_uris", {})
        if not image_uris and "card_faces" in card_json and card_json["card_faces"]:
            image_uris = card_json["card_faces"][0].get("image_uris", {})

        art_url = image_uris.get("art_crop")
        full_url = image_uris.get("normal")

        if art_url and not raw_art.exists():
            _download_image(art_url, raw_art)
        if full_url and not raw_full.exists():
            _download_image(full_url, raw_full)

    if mode == "real":
        if raw_full.exists():
            return raw_full
        placeholder = BUILT_DIR / f"{base_name}_real_placeholder.png"
        _placeholder_image(placeholder, spec.display_name, "Real card image missing", (744, 1039))
        return placeholder

    if not raw_art.exists():
        _placeholder_image(raw_art, spec.display_name, "Art crop missing", (672, 482))
    _build_abstract_card(spec, raw_art, built_abstract)
    return built_abstract


# ============================================================================
# Visual helpers
# ============================================================================


class Theme:
    BG = "#0F1320"
    TITLE = "#F4E8C1"
    SUBTITLE = "#B8C3E2"
    CARD_NODE = BLUE_D
    COMBO_NODE = ORANGE
    FEATURE_NODE = GREEN_D
    EDGE = GREY_B
    HILITE = YELLOW
    BAD = RED
    GOOD = GREEN


def node_box(label: str, color, width: float = 2.6, height: float = 0.9, font_size: int = 24) -> VGroup:
    box = RoundedRectangle(width=width, height=height, corner_radius=0.15, color=color, stroke_width=3)
    box.set_fill(color, opacity=0.15)
    txt = Text(label, font_size=font_size, color=WHITE)
    txt.move_to(box.get_center())
    return VGroup(box, txt)


def title_block(main: str, sub: str) -> VGroup:
    t = Text(main, font_size=46, color=Theme.TITLE)
    s = Text(sub, font_size=26, color=Theme.SUBTITLE)
    s.next_to(t, DOWN, buff=0.25)
    return VGroup(t, s)


def variant_chip(text: str, color=BLUE_D, font_size: int = 22) -> VGroup:
    rect = RoundedRectangle(width=3.6, height=0.56, corner_radius=0.12, color=color, stroke_width=2)
    rect.set_fill(color, opacity=0.2)
    lbl = Text(text, font_size=font_size, color=WHITE)
    lbl.move_to(rect.get_center())
    return VGroup(rect, lbl)


def make_card_sprite(card_key: str, scale: float = 0.28) -> Group:
    spec = CARD_SPECS[card_key]
    path = _ensure_card_asset(spec, CARD_MODE)
    from manim import ImageMobject

    img = ImageMobject(str(path))
    img.scale_to_fit_height(2.8 * scale / 0.28)

    caption = Text(spec.display_name, font_size=18, color=WHITE)
    caption.next_to(img, DOWN, buff=0.08)
    return Group(img, caption)


# ============================================================================
# Graph layout helpers
# ============================================================================

CARD_R  = 0.48   # card circle radius
COMBO_R = 0.54   # combo circle radius
FEAT_W  = 2.6    # feature ellipse width
FEAT_H  = 0.92   # feature ellipse height


def _fit_label(txt: Text, max_w: float) -> Text:
    """Scale text DOWN only — never upscale a short label to fill the container."""
    if txt.width > max_w:
        txt.scale_to_fit_width(max_w)
    return txt


# ---- Circle nodes (used in all scenes except DFS initial state) ----

def card_node(label: str) -> VGroup:
    shape = Circle(radius=CARD_R, color=BLUE_D, stroke_width=3)
    shape.set_fill(BLUE_D, opacity=0.4)
    txt = Text(label, font_size=38, color=WHITE)
    _fit_label(txt, CARD_R * 1.45)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


def combo_node(label: str) -> VGroup:
    shape = Circle(radius=COMBO_R, color=ORANGE, stroke_width=3)
    shape.set_fill(ORANGE, opacity=0.3)
    txt = Text(label, font_size=34, color=WHITE)
    _fit_label(txt, COMBO_R * 1.45)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


def feature_node(label: str) -> VGroup:
    shape = Ellipse(width=FEAT_W, height=FEAT_H, color=GREEN_D, stroke_width=3)
    shape.set_fill(GREEN_D, opacity=0.28)
    txt = Text(label, font_size=22, color=WHITE)
    _fit_label(txt, FEAT_W * 0.84)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


# ---- Square nodes (DFS scene initial state — morph to circles during traversal) ----

def card_sq(label: str) -> VGroup:
    shape = Square(side_length=CARD_R * 2.1, color=BLUE_D, stroke_width=3)
    shape.set_fill(BLUE_D, opacity=0.2)
    txt = Text(label, font_size=38, color=WHITE)
    _fit_label(txt, CARD_R * 1.45)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


def combo_sq(label: str) -> VGroup:
    shape = Square(side_length=COMBO_R * 2.1, color=ORANGE, stroke_width=3)
    shape.set_fill(ORANGE, opacity=0.18)
    txt = Text(label, font_size=34, color=WHITE)
    _fit_label(txt, COMBO_R * 1.45)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


def feature_sq(label: str) -> VGroup:
    shape = RoundedRectangle(width=FEAT_W, height=FEAT_H, corner_radius=0.08,
                              color=GREEN_D, stroke_width=3)
    shape.set_fill(GREEN_D, opacity=0.18)
    txt = Text(label, font_size=22, color=WHITE)
    _fit_label(txt, FEAT_W * 0.84)
    txt.move_to(shape.get_center())
    return VGroup(shape, txt)


def _node_radius(node: VGroup) -> float:
    """Return the effective radius of the node's shape for arrow buffering."""
    shape = node[0]
    # width/2 is safe for both circles and ellipses
    return shape.width / 2


def _edge_point(shape, toward: np.ndarray) -> np.ndarray:
    """Point on the boundary of `shape` (modelled as an ellipse from its bbox)
    along the ray from the shape's centre toward `toward`.

    Modelling every node as an ellipse — semi-axes width/2 and height/2 — makes
    arrows land ON the outline instead of stopping a full width short, which is
    what the old symmetric `buff=width/2` did to the wide feature ellipses.
    """
    c = shape.get_center()
    a = max(shape.width / 2, 1e-3)
    b = max(shape.height / 2, 1e-3)
    d = np.array(toward, dtype=float) - c
    n = float(np.linalg.norm(d[:2]))
    if n < 1e-6:
        return c
    d = d / n
    t = 1.0 / np.sqrt((d[0] / a) ** 2 + (d[1] / b) ** 2)
    return c + t * d


def narr(src: VGroup, tgt: VGroup, color=GREY_B, stroke_width=2.4, tip_length=0.20,
         gap: float = 0.06) -> Arrow:
    """Arrow drawn boundary-to-boundary between two nodes (never through them)."""
    s = _edge_point(src[0], tgt[0].get_center())
    e = _edge_point(tgt[0], src[0].get_center())
    d = e - s
    n = float(np.linalg.norm(d[:2]))
    if n > 2 * gap:                       # leave a hair of air at the arrowhead
        u = d / n
        s = s + u * gap
        e = e - u * gap
    return Arrow(s, e, buff=0.0, color=color, stroke_width=stroke_width, tip_length=tip_length)


def highlight_node(node: VGroup) -> SurroundingRectangle:
    return SurroundingRectangle(node[0], color=YELLOW, buff=0.1, stroke_width=5)


def morph_to_circle(scene: Scene, node: VGroup, color, radius: float, fill_opacity: float = 0.5):
    """Transform node[0] (square) → circle. The text node[1] stays in place."""
    circ = Circle(radius=radius, color=color, stroke_width=4)
    circ.set_fill(color, opacity=fill_opacity)
    circ.move_to(node[0].get_center())
    scene.play(Transform(node[0], circ), run_time=0.55)


# ============================================================================
# Scenes
# ============================================================================

# Commander Spellbook brand accents (from the frontend @theme palette):
#   primary lavender #c18aff  →  secondary coral #ff9595 (signature gradient).
BRAND_PRIMARY = "#c18aff"
BRAND_SECONDARY = "#ff9595"


class Scene00_Title(Scene):
    """Branded opening card: title, subtitle, and a tiny card→combo→feature motif."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("The Combo Graph", font_size=76, weight="BOLD")
        title.set_color_by_gradient(BRAND_PRIMARY, BRAND_SECONDARY)
        title.move_to(UP * 1.4)

        subtitle = Text(
            "How Commander Spellbook finds every card combination",
            font_size=28, color=Theme.SUBTITLE,
        )
        subtitle.next_to(title, DOWN, buff=0.45)

        # Tiny motif: card ──▶ combo ──▶ feature (the whole pipeline in miniature).
        card = card_node("A").scale(0.9)
        combo = combo_node("C").scale(0.9)
        feat = feature_node("Win").scale(0.9)
        motif = VGroup(card, combo, feat)
        motif.arrange(RIGHT, buff=1.5).move_to(DOWN * 1.7)
        e1 = narr(card, combo, color=GREY_A, stroke_width=3, tip_length=0.2)
        e2 = narr(combo, feat, color=GREY_A, stroke_width=3, tip_length=0.2)

        self.play(Write(title), run_time=1.4)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=0.8)
        self.play(
            LaggedStart(
                Create(card), Create(e1), Create(combo), Create(e2), Create(feat),
                lag_ratio=0.4,
            ),
            run_time=2.2,
        )
        self.wait(1.6)
        self.play(
            FadeOut(VGroup(title, subtitle, card, combo, feat, e1, e2)),
            run_time=0.8,
        )


class Scene01_GraphOverview(Scene):
    """Full graph: card circles, combo circles, feature ellipses, all edges."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("The Combo Graph", font_size=44, color=Theme.TITLE)
        title.to_edge(UP, buff=0.28)
        self.play(FadeIn(title, shift=DOWN * 0.3), run_time=0.7)

        # ---- Single card column so arrows NEVER cross ----
        # Cards are placed at y-levels that match the combo they feed,
        # eliminating the X-cross pattern of a 2-col layout.
        # A,B  → C1  (y ≈ +2.0)
        # C    → C2  (y ≈ +0.5)
        # D    → C3  (y ≈ -0.4)
        # E    → C4  (y ≈ -1.2)
        # X,Y  → C5  (y ≈ -2.5)
        # Cards: a single column of 7 (scaled down a touch so the column of
        # seven breathes). Grouped visually A,B | C | D | E | X,Y.
        cx = -5.0
        nA = card_node("A").scale(0.82).move_to(cx * RIGHT + UP * 2.35)
        nB = card_node("B").scale(0.82).move_to(cx * RIGHT + UP * 1.45)
        nC = card_node("C").scale(0.82).move_to(cx * RIGHT + UP * 0.55)
        nD = card_node("D").scale(0.82).move_to(cx * RIGHT + DOWN * 0.35)
        nE = card_node("E").scale(0.82).move_to(cx * RIGHT + DOWN * 1.25)
        nX = card_node("X").scale(0.82).move_to(cx * RIGHT + DOWN * 2.15)
        nY = card_node("Y").scale(0.82).move_to(cx * RIGHT + DOWN * 3.05)

        # Combo column: x=0; spread evenly so the five circles never touch.
        cC1 = combo_node("C1").move_to(UP * 2.15)
        cC2 = combo_node("C2").move_to(UP * 1.05)
        cC3 = combo_node("C3").move_to(DOWN * 0.05)
        cC4 = combo_node("C4").move_to(DOWN * 1.15)
        cC5 = combo_node("C5").move_to(DOWN * 2.25)

        # Feature column: x=5.0
        fIM = feature_node("Inf. Mana").move_to(RIGHT * 5.0 + UP * 1.35)
        fDD = feature_node("Draw Deck").move_to(RIGHT * 5.0 + DOWN * 0.1)
        fW  = feature_node("Win").move_to(RIGHT * 5.0 + DOWN * 1.55)

        lbl_cards  = Text("Cards",    font_size=18, color=BLUE_D).move_to(cx * RIGHT + UP * 3.05)
        lbl_combos = Text("Combos",   font_size=18, color=ORANGE).move_to(ORIGIN     + UP * 3.05)
        lbl_feats  = Text("Features", font_size=18, color=GREEN_D).move_to(RIGHT * 5.0 + UP * 3.05)

        # ---- Appear column by column ----
        self.play(FadeIn(lbl_cards), run_time=0.4)
        self.play(LaggedStart(
            Create(nA), Create(nB), Create(nC), Create(nD),
            Create(nE), Create(nX), Create(nY),
            lag_ratio=0.12,
        ), run_time=2.0)
        self.wait(0.8)

        self.play(FadeIn(lbl_combos), run_time=0.4)
        self.play(LaggedStart(
            Create(cC1), Create(cC2), Create(cC3), Create(cC4), Create(cC5),
            lag_ratio=0.18,
        ), run_time=1.6)
        self.wait(0.8)

        self.play(FadeIn(lbl_feats), run_time=0.4)
        self.play(LaggedStart(Create(fIM), Create(fDD), Create(fW), lag_ratio=0.2), run_time=1.0)
        self.wait(0.8)

        def _arr(src, tgt, col, sw=2.2):
            return narr(src, tgt, color=col, stroke_width=sw, tip_length=0.18)

        # ---- Card→Combo edges (blue): no crossings with single card column ----
        e_a_c1 = _arr(nA, cC1, BLUE_D); e_b_c1 = _arr(nB, cC1, BLUE_D)
        e_c_c2 = _arr(nC, cC2, BLUE_D)
        e_d_c3 = _arr(nD, cC3, BLUE_D)
        e_e_c4 = _arr(nE, cC4, BLUE_D)
        e_x_c5 = _arr(nX, cC5, BLUE_D); e_y_c5 = _arr(nY, cC5, BLUE_D)

        self.play(LaggedStart(
            Create(e_a_c1), Create(e_b_c1), Create(e_c_c2),
            Create(e_d_c3), Create(e_e_c4), Create(e_x_c5), Create(e_y_c5),
            lag_ratio=0.12,
        ), run_time=2.2)
        self.wait(0.8)

        # ---- Combo→Feature edges (green): combo produces feature ----
        e_c1_im = _arr(cC1, fIM, GREEN_D); e_c5_im = _arr(cC5, fIM, GREEN_D)
        e_c2_dd = _arr(cC2, fDD, GREEN_D)
        e_c3_w  = _arr(cC3, fW,  GREEN_D); e_c4_w  = _arr(cC4, fW, GREEN_D)

        self.play(LaggedStart(
            Create(e_c1_im), Create(e_c5_im), Create(e_c2_dd),
            Create(e_c3_w), Create(e_c4_w), lag_ratio=0.16,
        ), run_time=1.8)
        self.wait(0.5)

        # ---- Feature→Combo dependency edges (orange): feature is needed by combo ----
        e_im_c2 = _arr(fIM, cC2, ORANGE, 2.0)
        e_im_c4 = _arr(fIM, cC4, ORANGE, 2.0)
        e_dd_c3 = _arr(fDD, cC3, ORANGE, 2.0)

        self.play(LaggedStart(Create(e_im_c2), Create(e_im_c4), Create(e_dd_c3), lag_ratio=0.2),
                  run_time=1.4)

        caption = Text(
            "Cards → Combos → Features → more Combos",
            font_size=22, color=GREY_A,
        )
        caption.to_edge(DOWN, buff=0.25)
        self.play(FadeIn(caption), run_time=0.7)
        self.wait(3.0)


class Scene02_DownPhaseDFS(Scene):
    """
    DFS / down-phase animation that faithfully mirrors _combo_nodes_down:

    _combo_nodes_down(combo):
        1. For each needed card c: card_vs = {{c}}   (singleton, already known)
        2. For each needed feature f:
             feature_vs = _feature_down(f)
               _feature_down(f):
                 for each combo c2 producing f: combo_vs_i = _combo_nodes_down(c2)   [recurse]
                 feature_vs = UNION of all combo_vs_i   (OR)
        3. combo_vs = CARTESIAN PRODUCT of card_vss + feature_vss   (AND)

    Visual convention
    -----------------
    Nodes start as squares → morph to filled circles when the algorithm "visits" them.
    A yellow ring = currently being processed.
    Variant-set result boxes (rounded rects) accumulate next to each node.

    Edges (structural graph):
        card ──blue──►  combo   (card is ingredient of combo)
        combo ──green──► feature  (combo produces feature)
        feature ──orange──► combo  (feature is required by combo)
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _e(src: VGroup, tgt: VGroup, color=GREY_C, sw: float = 1.6) -> Arrow:
        """Structural faint arrow — boundary-to-boundary between nodes."""
        return narr(src, tgt, color=color, stroke_width=sw, tip_length=0.15)

    @staticmethod
    def _vbox(lines: list[str], col, width: float = 1.95) -> VGroup:
        """A small labelled result box listing variant sets."""
        height = 0.32 * len(lines) + 0.18
        box = RoundedRectangle(width=width, height=height, corner_radius=0.09,
                               color=col, stroke_width=2.0)
        box.set_fill(col, opacity=0.20)
        txts = VGroup(*[Text(ln, font_size=13, color=WHITE) for ln in lines])
        txts.arrange(DOWN, buff=0.05).move_to(box)
        return VGroup(box, txts)

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Down Phase:  variants of C3", font_size=34, color=Theme.TITLE)
        title.to_edge(UP, buff=0.22)
        self.play(FadeIn(title, shift=DOWN * 0.2), run_time=0.7)

        # ── Tree layout: depth DOWNWARD ─────────────────────────────────────
        #  Row y= 2.5   C3 (target)
        #  Row y= 1.3   D (card, right)   DrawDeck (feature, left)
        #  Row y= 0.1   C2 (combo)        C (card, right of C2)
        #  Row y=-1.1   InfMana (feature)
        #  Row y=-2.3   C1 (left)  C5 (right)
        #  Row y=-3.4   A B (below C1)   X Y (below C5)
        #
        # Result boxes placed away from neighbours:
        #   {D}         → RIGHT of D
        #   {C}         → RIGHT of C
        #   V(C1)       → LEFT of C1      (C1 is at x=-3.4 → box at ~x=-5.0, safe)
        #   {A}         → LEFT of A       (A at x=-4.6 → box at ~x=-6.0, fine)
        #   {B}         → RIGHT of B      (B at x=-2.6 → box at ~x=-1.0)
        #   V(C5)       → RIGHT of C5     (C5 at x=+0.8 → box at ~x=+2.3)
        #   {X}         → LEFT of X       (X at x=-0.4 → box at ~x=-1.9)
        #   {Y}         → RIGHT of Y      (Y at x=+1.8 → box at ~x=+3.3)
        #   V(InfMana)  → RIGHT of InfMana (x=-1.4 → box at ~x=+0.6)
        #   V(C2)       → LEFT of C2      (x=-1.4 → box at ~x=-3.2)
        #   V(DrawDeck) → LEFT of DrawDeck (x=-3.2 → box at ~x=-5.0)
        #   V(C3)       → RIGHT of C3     (x=0 → box at ~x=+1.6)

        nC3 = combo_sq("C3").move_to(RIGHT * 0.0  + UP * 2.45)
        nD  = card_sq("D")  .move_to(RIGHT * 2.9  + UP * 2.45)
        fDD = feature_sq("Draw Deck").move_to(LEFT * 3.1 + UP * 1.4)
        nC2 = combo_sq("C2").move_to(LEFT * 1.3   + UP * 0.35)
        nC  = card_sq("C")  .move_to(RIGHT * 1.4  + UP * 0.35)
        fIM = feature_sq("Inf. Mana").move_to(LEFT * 1.3 + DOWN * 0.7)
        nC1 = combo_sq("C1").move_to(LEFT * 3.3   + DOWN * 1.75)
        nC5 = combo_sq("C5").move_to(RIGHT * 0.7  + DOWN * 1.75)
        nA  = card_sq("A")  .move_to(LEFT * 4.5   + DOWN * 2.8)
        nB  = card_sq("B")  .move_to(LEFT * 2.6   + DOWN * 2.8)
        nX  = card_sq("X")  .move_to(LEFT * 0.4   + DOWN * 2.8)
        nY  = card_sq("Y")  .move_to(RIGHT * 1.7  + DOWN * 2.8)

        all_nodes = [nC3, nD, fDD, nC2, nC, fIM, nC1, nC5, nA, nB, nX, nY]

        e_d_c3  = self._e(nD,  nC3, BLUE_D)
        e_c_c2  = self._e(nC,  nC2, BLUE_D)
        e_a_c1  = self._e(nA,  nC1, BLUE_D)
        e_b_c1  = self._e(nB,  nC1, BLUE_D)
        e_x_c5  = self._e(nX,  nC5, BLUE_D)
        e_y_c5  = self._e(nY,  nC5, BLUE_D)
        e_c2_dd = self._e(nC2, fDD, GREEN_D)
        e_c1_im = self._e(nC1, fIM, GREEN_D)
        e_c5_im = self._e(nC5, fIM, GREEN_D)
        e_dd_c3 = self._e(fDD, nC3, ORANGE)
        e_im_c2 = self._e(fIM, nC2, ORANGE)

        all_edges = [e_d_c3, e_c_c2, e_a_c1, e_b_c1, e_x_c5, e_y_c5,
                     e_c2_dd, e_c1_im, e_c5_im, e_dd_c3, e_im_c2]

        legend = VGroup(
            Text("\u2501  card \u2192 combo (ingredient)",   font_size=12, color=BLUE_D),
            Text("\u2501  combo \u2192 feature (produces)",  font_size=12, color=GREEN_D),
            Text("\u2501  feature \u2192 combo (needed by)", font_size=12, color=ORANGE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.09)
        legend.to_corner(LEFT + UP, buff=0.3)

        intro = Text("Squares = unvisited.  Circles = visited.", font_size=16, color=GREY_A)
        intro.to_edge(DOWN, buff=0.22)

        self.play(LaggedStart(*[Create(n) for n in all_nodes], lag_ratio=0.06), run_time=1.8)
        self.play(LaggedStart(*[Create(e) for e in all_edges], lag_ratio=0.05), run_time=1.5)
        self.play(FadeIn(legend), FadeIn(intro), run_time=0.5)
        self.wait(1.0)
        self.play(FadeOut(intro), run_time=0.4)

        # ── Call-stack panel ──────────────────────────────────────────────────
        call_stack: list[Text] = []
        stack_panel = RoundedRectangle(width=2.7, height=3.55, corner_radius=0.09,
                                       color=GREY_C, stroke_width=1.0)
        stack_panel.set_fill("#12172A", opacity=0.94)
        stack_panel.to_corner(RIGHT + DOWN, buff=0.15)
        sp_title = Text("Call stack", font_size=14, color=GREY_A)
        sp_title.move_to(stack_panel.get_top() + DOWN * 0.26)
        self.play(FadeIn(stack_panel), FadeIn(sp_title), run_time=0.3)

        def push_call(label: str, col=WHITE):
            t = Text(f"  {label}", font_size=12, color=col)
            if call_stack:
                t.next_to(call_stack[-1], DOWN, buff=0.07, aligned_edge=LEFT)
            else:
                t.move_to(stack_panel.get_top() + DOWN * 0.55 + LEFT * 0.8)
            call_stack.append(t)
            self.play(FadeIn(t, shift=RIGHT * 0.08), run_time=0.22)

        def pop_call():
            if call_stack:
                t = call_stack.pop()
                self.play(FadeOut(t, shift=LEFT * 0.08), run_time=0.18)

        def focus(node: VGroup, col=YELLOW, lbl: str = ""):
            ring = SurroundingRectangle(node[0], color=col, buff=0.08, stroke_width=4)
            anims = [Create(ring)]
            caption = None
            if lbl:
                caption = Text(lbl, font_size=13, color=col)
                caption.next_to(ring, DOWN, buff=0.07)
                anims.append(FadeIn(caption))
            self.play(*anims, run_time=0.35)
            self.wait(0.15)
            return ring, caption

        def unfocus(ring, caption=None):
            anims = [FadeOut(ring)]
            if caption:
                anims.append(FadeOut(caption))
            self.play(*anims, run_time=0.18)

        def visit_circle(node: VGroup, col, radius: float, opacity: float = 0.55):
            circ = Circle(radius=radius, color=col, stroke_width=3)
            circ.set_fill(col, opacity=opacity)
            circ.move_to(node[0].get_center())
            self.play(Transform(node[0], circ), run_time=0.38)

        def show_vs(node: VGroup, lines: list[str], col, side=LEFT,
                    width: float = 2.0) -> VGroup:
            box = self._vbox(lines, col, width)
            box.next_to(node[0], side, buff=0.16)
            shift_dir = RIGHT * 0.1 if side is LEFT else LEFT * 0.1
            self.play(FadeIn(box, shift=shift_dir), run_time=0.30)
            return box

        def note(msg: str, col=GREY_A):
            t = Text(msg, font_size=16, color=col)
            t.to_edge(DOWN, buff=0.18)
            self.play(FadeIn(t), run_time=0.25)
            self.wait(0.45)
            self.play(FadeOut(t), run_time=0.22)

        # ═════════════════════════════════════════════════════════════════════
        # _combo_nodes_down(C3)
        # ═════════════════════════════════════════════════════════════════════
        note("_combo_nodes_down(C3) — start here", YELLOW)
        ring_c3, cap_c3 = focus(nC3, YELLOW, "_combo_nodes_down(C3)")
        push_call("_combo_down(C3)", ORANGE)
        visit_circle(nC3, ORANGE, COMBO_R)
        self.wait(0.3)

        # Step 1: card D → singleton {D}
        note("Step 1: card D is needed by C3  →  V = {D}", BLUE_D)
        ring_d, cap_d = focus(nD, BLUE_D, "card D")
        visit_circle(nD, BLUE_D, CARD_R)
        show_vs(nD, ["{D}"], BLUE_D, RIGHT, 1.3)
        unfocus(ring_d, cap_d)
        self.wait(0.2)

        # Step 2: feature DrawDeck needed by C3
        note("Step 2: Draw Deck is needed by C3  →  _feature_down", ORANGE)
        ring_dd, cap_dd = focus(fDD, ORANGE, "need: Draw Deck")
        push_call("  _feature_down(DrawDeck)", GREEN_D)
        visit_circle(fDD, GREEN_D, FEAT_H * 0.44)
        self.wait(0.25)

        # DrawDeck produced by C2
        note("Draw Deck is produced by C2  →  recurse into C2", GREEN_D)
        ring_c2, cap_c2 = focus(nC2, YELLOW, "_combo_nodes_down(C2)")
        push_call("    _combo_down(C2)", ORANGE)
        visit_circle(nC2, ORANGE, COMBO_R)
        self.wait(0.25)

        # Step 2a: card C needed by C2
        note("Step 2a: card C is needed by C2  →  V = {C}", BLUE_D)
        ring_c, cap_c = focus(nC, BLUE_D, "card C")
        visit_circle(nC, BLUE_D, CARD_R)
        show_vs(nC, ["{C}"], BLUE_D, RIGHT, 1.3)
        unfocus(ring_c, cap_c)
        self.wait(0.2)

        # Step 2b: InfMana needed by C2
        note("Step 2b: Inf. Mana is needed by C2  →  _feature_down", ORANGE)
        ring_im, cap_im = focus(fIM, ORANGE, "need: Inf. Mana")
        push_call("      _feature_down(InfMana)", GREEN_D)
        visit_circle(fIM, GREEN_D, FEAT_H * 0.44)
        self.wait(0.25)

        # InfMana produced by C1 and C5
        note("Inf. Mana produced by C1 AND C5  →  recurse into both", GREEN_D)

        # Recurse C1
        ring_c1, cap_c1 = focus(nC1, YELLOW, "_combo_nodes_down(C1)")
        push_call("        _combo_down(C1)", ORANGE)
        visit_circle(nC1, ORANGE, COMBO_R)
        self.wait(0.25)
        note("C1 needs A and B  →  singletons {A} and {B}", BLUE_D)
        ring_a, cap_a = focus(nA, BLUE_D, "card A")
        visit_circle(nA, BLUE_D, CARD_R)
        unfocus(ring_a, cap_a)
        ring_b, cap_b = focus(nB, BLUE_D, "card B")
        visit_circle(nB, BLUE_D, CARD_R)
        unfocus(ring_b, cap_b)
        note("AND: {A} \u2297 {B}  \u2192  V(C1) = {A,B}", ORANGE)
        show_vs(nC1, ["V(C1)", "{A,B}"], ORANGE, LEFT)
        unfocus(ring_c1, cap_c1); pop_call()
        self.wait(0.25)

        # Recurse C5
        ring_c5, cap_c5 = focus(nC5, YELLOW, "_combo_nodes_down(C5)")
        push_call("        _combo_down(C5)", ORANGE)
        visit_circle(nC5, ORANGE, COMBO_R)
        self.wait(0.25)
        note("C5 needs X and Y  →  singletons {X} and {Y}", BLUE_D)
        ring_x, cap_x = focus(nX, BLUE_D, "card X")
        visit_circle(nX, BLUE_D, CARD_R)
        unfocus(ring_x, cap_x)
        ring_y, cap_y = focus(nY, BLUE_D, "card Y")
        visit_circle(nY, BLUE_D, CARD_R)
        unfocus(ring_y, cap_y)
        note("AND: {X} \u2297 {Y}  \u2192  V(C5) = {X,Y}", ORANGE)
        show_vs(nC5, ["V(C5)", "{X,Y}"], ORANGE, RIGHT)
        unfocus(ring_c5, cap_c5); pop_call()
        self.wait(0.25)

        # OR for InfMana
        note("OR: V(C1) \u222a V(C5)  \u2192  V(InfMana) = {A,B} \u222a {X,Y}", GREEN_D)
        show_vs(fIM, ["V(InfMana)", "{A,B}", "{X,Y}"], GREEN_D, RIGHT)
        unfocus(ring_im, cap_im); pop_call()
        self.wait(0.3)

        # AND for C2
        note("AND: {C} \u2297 V(InfMana)  \u2192  V(C2) = {A,B,C} \u222a {X,Y,C}", ORANGE)
        show_vs(nC2, ["V(C2)", "{A,B,C}", "{X,Y,C}"], ORANGE, LEFT)
        unfocus(ring_c2, cap_c2); pop_call()
        self.wait(0.3)

        # OR for DrawDeck
        note("OR: V(C2)  \u2192  V(DrawDeck) = {A,B,C} \u222a {X,Y,C}", GREEN_D)
        show_vs(fDD, ["V(DrawDeck)", "{A,B,C}", "{X,Y,C}"], GREEN_D, LEFT)
        unfocus(ring_dd, cap_dd); pop_call()
        self.wait(0.3)

        # Final AND for C3
        note("AND: {D} \u2297 V(DrawDeck)  \u2192  V(C3) = {A,B,C,D} \u222a {X,Y,C,D}", YELLOW)
        show_vs(nC3, ["V(C3)", "{A,B,C,D}", "{X,Y,C,D}"], YELLOW, RIGHT)
        unfocus(ring_c3, cap_c3); pop_call()
        self.wait(0.4)

        final = Text("V(C3) = { {A,B,C,D},  {X,Y,C,D} }   \u2014 two minimal variants",
                     font_size=20, color=GREEN)
        final.to_edge(DOWN, buff=0.18)
        self.play(FadeIn(final), run_time=0.55)
        self.wait(3.5)


class Scene03_VariantSetsGeometric(Scene):
    """OR and AND set operations shown geometrically."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Variant Sets: OR and AND", font_size=42, color=Theme.TITLE)
        title.to_edge(UP, buff=0.3)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.5)

        # ---- OR: two combos both producing InfMana ----
        or_lbl = Text("OR — union of alternative providers", font_size=26, color=GREEN_D)
        or_lbl.move_to(UP * 2.1)
        self.play(FadeIn(or_lbl), run_time=0.6)
        self.wait(0.4)

        c1 = combo_node("C1").move_to(LEFT * 4.0 + UP * 0.8)
        c5 = combo_node("C5").move_to(LEFT * 4.0 + DOWN * 0.5)
        fim = feature_node("Inf. Mana").move_to(LEFT * 0.5 + UP * 0.15)

        # Variant set bubbles on the left of C1 and C5
        def vset(txt, col, pos):
            box = RoundedRectangle(width=1.8, height=0.52, corner_radius=0.1,
                                   color=col, stroke_width=2)
            box.set_fill(col, opacity=0.25)
            box.move_to(pos)
            lbl = Text(txt, font_size=18, color=WHITE).move_to(box)
            return VGroup(box, lbl)

        v1 = vset("{A,B}", BLUE_D, LEFT * 6.2 + UP * 0.8)
        v5 = vset("{X,Y}", BLUE_D, LEFT * 6.2 + DOWN * 0.5)

        a1 = narr(c1, fim, color=GREEN_D, stroke_width=2.2, tip_length=0.18)
        a5 = narr(c5, fim, color=GREEN_D, stroke_width=2.2, tip_length=0.18)

        self.play(Create(c1), Create(c5), run_time=0.7)
        self.play(Create(v1), Create(v5), run_time=0.6)
        self.play(Create(a1), Create(a5), Create(fim), run_time=0.8)
        self.wait(0.5)

        # Union result box to the right of InfMana
        union_box = RoundedRectangle(width=2.3, height=1.0, corner_radius=0.1,
                                     color=GREEN_D, stroke_width=2.5)
        union_box.set_fill(GREEN_D, opacity=0.2)
        union_box.move_to(RIGHT * 3.2 + UP * 0.15)
        u1 = Text("{A,B}", font_size=18, color=WHITE)
        u2 = Text("{X,Y}", font_size=18, color=WHITE)
        VGroup(u1, u2).arrange(DOWN, buff=0.1).move_to(union_box)
        u_title = Text("V(Inf.Mana)", font_size=15, color=GREEN_D).next_to(union_box, UP, buff=0.07)
        u_eq = Text("= {A,B} ∪ {X,Y}", font_size=18, color=GREEN_D).next_to(union_box, DOWN, buff=0.1)

        self.play(Create(union_box), FadeIn(u_title), run_time=0.5)
        self.play(FadeIn(u1), FadeIn(u2), FadeIn(u_eq), run_time=0.5)
        self.wait(1.5)

        self.play(FadeOut(VGroup(or_lbl, c1, c5, fim, v1, v5, a1, a5,
                                  union_box, u_title, u1, u2, u_eq)), run_time=0.7)
        self.wait(0.3)

        # ---- AND: C2 needs card C AND InfMana feature ----
        and_lbl = Text("AND — cross-product of card sets and feature variants", font_size=24, color=ORANGE)
        and_lbl.move_to(UP * 2.1)
        self.play(FadeIn(and_lbl), run_time=0.6)
        self.wait(0.4)

        c2 = combo_node("C2").move_to(ORIGIN + UP * 0.2)

        card_box = RoundedRectangle(width=1.8, height=0.55, corner_radius=0.1,
                                    color=BLUE_D, stroke_width=2)
        card_box.set_fill(BLUE_D, opacity=0.25)
        card_box.move_to(LEFT * 4.0 + UP * 1.0)
        card_lbl = Text("{C}", font_size=20, color=WHITE).move_to(card_box)
        card_title = Text("cards needed", font_size=14, color=BLUE_D).next_to(card_box, UP, buff=0.07)

        feat_box = RoundedRectangle(width=2.3, height=1.0, corner_radius=0.1,
                                    color=GREEN_D, stroke_width=2)
        feat_box.set_fill(GREEN_D, opacity=0.22)
        feat_box.move_to(LEFT * 4.0 + DOWN * 0.6)
        f1 = Text("{A,B}", font_size=18, color=WHITE)
        f2 = Text("{X,Y}", font_size=18, color=WHITE)
        VGroup(f1, f2).arrange(DOWN, buff=0.1).move_to(feat_box)
        feat_title = Text("V(Inf.Mana)", font_size=14, color=GREEN_D).next_to(feat_box, UP, buff=0.07)

        ec = Arrow(card_box.get_right(), c2[0].get_center(),
                   buff=_node_radius(c2), color=BLUE_D, stroke_width=2.2, tip_length=0.18)
        ef = Arrow(feat_box.get_right(), c2[0].get_center(),
                   buff=_node_radius(c2), color=GREEN_D, stroke_width=2.2, tip_length=0.18)

        self.play(Create(card_box), FadeIn(card_lbl), FadeIn(card_title), run_time=0.6)
        self.play(Create(feat_box), FadeIn(f1), FadeIn(f2), FadeIn(feat_title), run_time=0.7)
        self.play(Create(c2), Create(ec), Create(ef), run_time=0.8)
        self.wait(0.7)

        # Cross product result
        prod_box = RoundedRectangle(width=2.6, height=1.1, corner_radius=0.1,
                                    color=ORANGE, stroke_width=2.5)
        prod_box.set_fill(ORANGE, opacity=0.22)
        prod_box.move_to(RIGHT * 3.5 + UP * 0.2)
        pr1 = Text("{A,B,C}", font_size=18, color=WHITE)
        pr2 = Text("{X,Y,C}", font_size=18, color=WHITE)
        VGroup(pr1, pr2).arrange(DOWN, buff=0.12).move_to(prod_box)
        prod_title = Text("V(C2)", font_size=15, color=ORANGE).next_to(prod_box, UP, buff=0.07)
        prod_eq = Text("{C} × V(Inf.Mana)", font_size=16, color=ORANGE).next_to(prod_box, DOWN, buff=0.1)

        self.play(Create(prod_box), FadeIn(prod_title), FadeIn(prod_eq), run_time=0.6)
        self.play(FadeIn(pr1), FadeIn(pr2), run_time=0.5)
        self.wait(2.5)


class Scene04_MinimalSets(Scene):
    """Minimality / antichain pruning visualized geometrically."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Minimality Pruning", font_size=42, color=Theme.TITLE)
        title.to_edge(UP, buff=0.3)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.4)

        rule_txt = Text(
            "Keep variants that are NOT a superset of any already-kept variant.",
            font_size=23, color=GREY_A,
        )
        rule_txt.next_to(title, DOWN, buff=0.3)
        self.play(FadeIn(rule_txt), run_time=0.7)
        self.wait(0.8)

        def vbox(txt, col, pos):
            b = RoundedRectangle(width=2.6, height=0.58, corner_radius=0.1,
                                  color=col, stroke_width=3)
            b.set_fill(col, opacity=0.22)
            b.move_to(pos)
            t = Text(txt, font_size=19, color=WHITE)
            _fit_label(t, 2.3)
            t.move_to(b)
            return VGroup(b, t)

        # ---- Case 1: superset discarded ----
        c1_lbl = Text("Case 1 — candidate is a superset → discard it", font_size=24, color=WHITE)
        c1_lbl.move_to(UP * 1.2)
        self.play(FadeIn(c1_lbl), run_time=0.6)

        kept = vbox("{A,B,C,D}", GREEN, LEFT * 3.5 + UP * 0.2)
        cand = vbox("{A,B,C,D,E}", RED, RIGHT * 2.5 + UP * 0.2)
        kept_lbl = Text("kept", font_size=14, color=GREEN).next_to(kept, UP, buff=0.07)
        cand_lbl = Text("candidate", font_size=14, color=RED).next_to(cand, UP, buff=0.07)

        self.play(Create(kept), FadeIn(kept_lbl), run_time=0.5)
        self.wait(0.4)
        self.play(Create(cand), FadeIn(cand_lbl), run_time=0.5)
        self.wait(0.4)

        sub_arrow = Arrow(kept[0].get_right(), cand[0].get_left(), buff=0.12,
                          color=YELLOW, stroke_width=3, tip_length=0.18)
        sub_eq = Text("⊆", font_size=28, color=YELLOW).next_to(sub_arrow, UP, buff=0.08)
        self.play(Create(sub_arrow), FadeIn(sub_eq), run_time=0.55)
        self.wait(0.5)

        x1 = Line(cand[0].get_corner(UP + LEFT), cand[0].get_corner(DOWN + RIGHT), color=RED, stroke_width=7)
        x2 = Line(cand[0].get_corner(UP + RIGHT), cand[0].get_corner(DOWN + LEFT), color=RED, stroke_width=7)
        self.play(Create(x1), Create(x2), run_time=0.45)
        self.play(FadeOut(VGroup(cand, cand_lbl, x1, x2), shift=DOWN * 0.3), run_time=0.45)
        self.wait(0.6)
        # Clear the whole Case-1 tableau so no arrow is left pointing at nothing.
        self.play(FadeOut(VGroup(c1_lbl, kept, kept_lbl, sub_arrow, sub_eq)), run_time=0.5)
        self.wait(0.3)

        # ---- Case 2: subset displaces supersets ----
        c2_lbl = Text("Case 2 — candidate is a subset → keep it, remove supersets", font_size=24, color=WHITE)
        c2_lbl.move_to(UP * 1.4)
        self.play(FadeIn(c2_lbl), run_time=0.7)

        old1 = vbox("{A,B,C,D}", BLUE_D, LEFT * 3.8 + UP * 0.2)
        old2 = vbox("{X,Y,C,D}", BLUE_D, RIGHT * 2.0 + UP * 0.2)
        new  = vbox("{A,B,C}",   GREEN,  LEFT * 0.9 + DOWN * 1.3)
        new_lbl = Text("new candidate", font_size=14, color=GREEN).next_to(new, DOWN, buff=0.07)

        self.play(Create(old1), Create(old2), run_time=0.7)
        self.wait(0.3)
        self.play(FadeIn(new, shift=UP * 0.2), FadeIn(new_lbl), run_time=0.5)
        self.wait(0.4)

        arr1 = Arrow(new[0].get_left(), old1[0].get_bottom(), buff=0.1,
                     color=YELLOW, stroke_width=2.5, tip_length=0.15)
        self.play(Create(arr1), run_time=0.45)
        self.wait(0.3)

        y1 = Line(old1[0].get_corner(UP + LEFT), old1[0].get_corner(DOWN + RIGHT), color=RED, stroke_width=7)
        y2 = Line(old1[0].get_corner(UP + RIGHT), old1[0].get_corner(DOWN + LEFT), color=RED, stroke_width=7)
        self.play(Create(y1), Create(y2), run_time=0.4)
        self.play(FadeOut(VGroup(old1, y1, y2, arr1), shift=UP * 0.2), run_time=0.45)

        glow = SurroundingRectangle(new, color=GREEN, buff=0.1, stroke_width=5)
        self.play(Create(glow), run_time=0.45)
        self.wait(2.5)


class Scene04b_TwoFeatureMerge(Scene):
    """
    The interesting down-phase case: a combo C0 needs TWO features, and each
    feature already resolved to MORE THAN ONE recipe. AND-merging them is a
    cross-product (union every pair), and one product turns out to be a subset
    of another — so minimality prunes the superset.

        V(F1) = { {A,B}, {C,D} }
        V(F2) = { {A,B,E}, {G} }

        cross-product (∪ each pair):
                       {A,B,E}          {G}
            {A,B}  →   {A,B,E}          {A,B,G}
            {C,D}  →   {A,B,C,D,E}      {C,D,G}

        {A,B,E} ⊆ {A,B,C,D,E}   →  drop {A,B,C,D,E}
        V(C0) = { {A,B,E}, {A,B,G}, {C,D,G} }
    """

    # Column (F2) and row (F1) anchors for the multiplication-table layout.
    COL_X = (-1.1, 2.1)
    ROW_Y = (0.15, -1.35)
    HDR_Y = 1.5
    HDR_X = -4.3

    def _cell(self, txt, col, pos, w=2.7, h=0.9, fs=23):
        box = RoundedRectangle(width=w, height=h, corner_radius=0.1, color=col, stroke_width=2.5)
        box.set_fill(col, opacity=0.22)
        label = Text(txt, font_size=fs, color=WHITE)
        _fit_label(label, w - 0.3)
        label.move_to(box)
        return VGroup(box, label).move_to(pos)

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Down Phase: merging two features", font_size=36, color=Theme.TITLE)
        title.to_edge(UP, buff=0.24)
        self.play(FadeIn(title, shift=DOWN * 0.2), run_time=0.7)

        stmt = Text("Combo C0 needs feature F1  AND  feature F2",
                    font_size=25, color=Theme.SUBTITLE,
                    t2c={"F1": BLUE_D, "F2": GREEN_D, "C0": ORANGE})
        stmt.next_to(title, DOWN, buff=0.22)
        caption = Text("rows = F1's recipes      columns = F2's recipes",
                       font_size=17, color=GREY_A, t2c={"F1": BLUE_D, "F2": GREEN_D})
        caption.next_to(stmt, DOWN, buff=0.16)
        self.play(FadeIn(stmt), run_time=0.5)
        self.play(FadeIn(caption), run_time=0.4)
        self.wait(0.4)

        # ── Corner + headers ────────────────────────────────────────────────
        corner = self._cell("∪", GREY_C, self.HDR_X * RIGHT + self.HDR_Y * UP,
                            w=1.5, h=0.9, fs=30)

        # Row headers = V(F1) recipes (blue)
        rh = [
            self._cell("{A,B}", BLUE_D, self.HDR_X * RIGHT + self.ROW_Y[0] * UP, w=1.5),
            self._cell("{C,D}", BLUE_D, self.HDR_X * RIGHT + self.ROW_Y[1] * UP, w=1.5),
        ]
        # Column headers = V(F2) recipes (green)
        ch = [
            self._cell("{A,B,E}", GREEN_D, self.COL_X[0] * RIGHT + self.HDR_Y * UP),
            self._cell("{G}",     GREEN_D, self.COL_X[1] * RIGHT + self.HDR_Y * UP),
        ]

        self.play(FadeIn(corner), run_time=0.3)
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * 0.2) for b in rh], lag_ratio=0.3),
                  run_time=0.8)
        self.play(LaggedStart(*[FadeIn(b, shift=DOWN * 0.2) for b in ch], lag_ratio=0.3),
                  run_time=0.8)
        self.wait(0.5)

        note = Text("AND  ⇒  cross-product: union of every (row, column) pair",
                    font_size=20, color=ORANGE)
        note.to_edge(DOWN, buff=0.3)
        self.play(FadeIn(note), run_time=0.5)
        self.wait(0.4)

        # ── Body cells (the four unions) ────────────────────────────────────
        results = [
            [("{A,B,E}", False), ("{A,B,G}", False)],
            [("{A,B,C,D,E}", True), ("{C,D,G}", False)],   # [1][0] is the superset
        ]
        cells: list[list[VGroup]] = [[None, None], [None, None]]
        for r in range(2):
            for c in range(2):
                txt, _ = results[r][c]
                pos = self.COL_X[c] * RIGHT + self.ROW_Y[r] * UP
                cell = self._cell(txt, GREY_B, pos)
                cells[r][c] = cell
                # flash the contributing headers as each product forms
                self.play(
                    rh[r][0].animate.set_stroke(YELLOW, width=4),
                    ch[c][0].animate.set_stroke(YELLOW, width=4),
                    run_time=0.2,
                )
                self.play(FadeIn(cell, scale=0.85), run_time=0.3)
                self.play(
                    rh[r][0].animate.set_stroke(BLUE_D, width=2.5),
                    ch[c][0].animate.set_stroke(GREEN_D, width=2.5),
                    run_time=0.2,
                )
        self.wait(0.6)
        self.play(FadeOut(note), run_time=0.3)

        # ── Minimality: {A,B,E} ⊆ {A,B,C,D,E} → drop the superset ───────────
        sub = cells[0][0]      # {A,B,E}
        sup = cells[1][0]      # {A,B,C,D,E}
        min_note = Text("Keep only minimal sets:", font_size=22, color=YELLOW)
        min_note.to_edge(DOWN, buff=0.55)
        self.play(FadeIn(min_note), run_time=0.4)

        ring_sub = SurroundingRectangle(sub, color=GREEN, buff=0.06, stroke_width=4)
        ring_sup = SurroundingRectangle(sup, color=RED, buff=0.06, stroke_width=4)
        self.play(Create(ring_sub), Create(ring_sup), run_time=0.5)

        rel = Text("{A,B,E}  ⊆  {A,B,C,D,E}", font_size=24, color=WHITE,
                   t2c={"{A,B,E}": GREEN, "{A,B,C,D,E}": RED})
        rel.to_edge(DOWN, buff=0.15)
        self.play(FadeIn(rel), run_time=0.5)
        self.wait(0.8)

        x1 = Line(sup[0].get_corner(UP + LEFT), sup[0].get_corner(DOWN + RIGHT),
                  color=RED, stroke_width=7)
        x2 = Line(sup[0].get_corner(UP + RIGHT), sup[0].get_corner(DOWN + LEFT),
                  color=RED, stroke_width=7)
        self.play(Create(x1), Create(x2), run_time=0.4)
        self.play(
            FadeOut(VGroup(sup, x1, x2, ring_sup, ring_sub), shift=DOWN * 0.3),
            FadeOut(VGroup(min_note, rel)),
            run_time=0.5,
        )
        self.wait(0.3)

        # ── Final variant set of C0 ─────────────────────────────────────────
        survivors = VGroup(cells[0][0], cells[0][1], cells[1][1])
        result_lbl = Text("V(C0) = 3 minimal recipes", font_size=24, color=ORANGE,
                          t2c={"C0": ORANGE})
        result_lbl.to_edge(DOWN, buff=0.35)
        glow = SurroundingRectangle(survivors, color=ORANGE, buff=0.16, stroke_width=4)
        self.play(Create(glow), FadeIn(result_lbl), run_time=0.7)
        self.wait(3.0)


class Scene05_UpPhase(Scene):
    """Up phase: from ingredient cards, propagate upward through the graph."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Up Phase — From Cards to Outcomes", font_size=38, color=Theme.TITLE)
        title.to_edge(UP, buff=0.3)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.4)

        # ---- Node layout: cards bottom, combos middle, features top ----
        # Cards row (y=-3.0)
        nA = card_node("A").move_to(LEFT * 5.0 + DOWN * 3.0)
        nB = card_node("B").move_to(LEFT * 3.2 + DOWN * 3.0)
        nC = card_node("C").move_to(LEFT * 1.4 + DOWN * 3.0)
        nD = card_node("D").move_to(RIGHT * 0.4 + DOWN * 3.0)
        nE = card_node("E").move_to(RIGHT * 2.2 + DOWN * 3.0)
        nX = card_node("X").move_to(RIGHT * 4.0 + DOWN * 3.0)
        nY = card_node("Y").move_to(RIGHT * 5.8 + DOWN * 3.0)

        # Combos row (y=-1.0)
        cC1 = combo_node("C1").move_to(LEFT * 4.0 + DOWN * 1.0)
        cC5 = combo_node("C5").move_to(RIGHT * 5.0 + DOWN * 1.0)
        cC2 = combo_node("C2").move_to(LEFT * 1.2 + DOWN * 1.0)
        cC3 = combo_node("C3").move_to(LEFT * 1.2 + UP * 0.8)
        cC4 = combo_node("C4").move_to(RIGHT * 2.8 + DOWN * 1.0)

        # Features row (y=+1.5 to +2.5)
        fIM = feature_node("Inf. Mana").move_to(LEFT * 4.0 + UP * 1.6)
        fDD = feature_node("Draw Deck").move_to(LEFT * 1.2 + UP * 2.5)
        fW  = feature_node("Win").move_to(RIGHT * 2.0 + UP * 2.5)

        # Show all nodes
        all_nodes_out = [nE, nX, nY]

        self.play(LaggedStart(*[Create(n) for n in [nA,nB,nC,nD,nE,nX,nY]], lag_ratio=0.09), run_time=1.4)
        self.play(LaggedStart(*[Create(n) for n in [cC1,cC5,cC2,cC3,cC4]], lag_ratio=0.1), run_time=1.1)
        self.play(LaggedStart(*[Create(n) for n in [fIM,fDD,fW]], lag_ratio=0.14), run_time=0.9)

        # Dim out-of-hand cards
        self.play(*[n.animate.set_opacity(0.22) for n in all_nodes_out], run_time=0.6)

        hand_lbl = Text("Hand: {A, B, C, D}", font_size=22, color=BLUE_D)
        hand_lbl.to_edge(DOWN, buff=0.18)
        self.play(FadeIn(hand_lbl), run_time=0.5)
        self.wait(0.7)

        # Faint structural edges: card→combo (ingredient), feature→combo (needed by)
        def fe(src, tgt, col=GREY_B):
            return narr(src, tgt, color=col, stroke_width=1.5, tip_length=0.13)

        struct = VGroup(
            fe(nA, cC1), fe(nB, cC1),
            fe(nX, cC5), fe(nY, cC5),
            fe(nC, cC2), fe(nD, cC3), fe(nE, cC4),
        )
        self.play(LaggedStart(*[Create(e) for e in struct], lag_ratio=0.07), run_time=1.3)
        self.wait(0.5)

        # Helper: bold activation arrow (arrows point toward the target)
        def act(src, tgt, col=YELLOW):
            a = narr(src, tgt, color=col, stroke_width=3.8, tip_length=0.20)
            self.play(Create(a), run_time=0.45)
            return a

        def light(node: VGroup, col):
            node[0].set_fill(col, opacity=0.58)
            node[0].set_stroke(col, width=4)
            self.play(node[0].animate.set_fill(col, opacity=0.58), run_time=0.35)

        step = Text("", font_size=20, color=WHITE).to_edge(DOWN, buff=0.45)

        def show_step(msg):
            nonlocal step
            new_step = Text(msg, font_size=20, color=WHITE).to_edge(DOWN, buff=0.45)
            self.play(FadeOut(step), FadeIn(new_step), run_time=0.35)
            step = new_step

        # Step 1: A+B → C1 → InfMana
        show_step("A + B  →  C1 fires  →  Infinite Mana unlocked")
        self.play(FadeOut(hand_lbl), run_time=0.2)
        act(nA, cC1); act(nB, cC1)
        self.wait(0.2); light(cC1, ORANGE)
        act(cC1, fIM, GREEN_D); light(fIM, GREEN_D)
        self.wait(0.9)

        # Step 2: C + InfMana → C2 → DrawDeck
        show_step("C + Inf.Mana  →  C2 fires  →  Draw Deck unlocked")
        act(nC, cC2)
        act_im = narr(fIM, cC2, color=GREEN_D, stroke_width=3.8, tip_length=0.20)
        self.play(Create(act_im), run_time=0.45)
        self.wait(0.2); light(cC2, ORANGE)
        act(cC2, fDD, GREEN_D); light(fDD, GREEN_D)
        self.wait(0.9)

        # Step 3: D + DrawDeck → C3 → Win
        show_step("D + Draw Deck  →  C3 fires  →  Win unlocked!")
        act(nD, cC3)
        act_dd = narr(fDD, cC3, color=GREEN_D, stroke_width=3.8, tip_length=0.20)
        self.play(Create(act_dd), run_time=0.45)
        self.wait(0.2); light(cC3, ORANGE)
        act(cC3, fW, GREEN_D); light(fW, GREEN_D)
        self.wait(0.9)

        # C4 and C5 remain unreachable
        show_step("C4 and C5 cannot fire — E, X, Y not in hand.")
        for n in [cC4, cC5]:
            n[0].set_stroke(RED, width=3)
            self.play(n[0].animate.set_fill(RED, opacity=0.18), run_time=0.4)
        self.wait(0.8)

        final = Text("Result: Win reachable with {A, B, C, D}", font_size=24, color=GREEN)
        final.to_edge(DOWN, buff=0.22)
        self.play(FadeOut(step), FadeIn(final), run_time=0.55)
        self.wait(3.0)


class Scene06_DownVsUp(Scene):
    """Side-by-side: down phase (DFS from target) vs up phase (BFS from ingredients)."""

    def construct(self):
        self.camera.background_color = Theme.BG

        title = Text("Down Phase  vs  Up Phase", font_size=42, color=Theme.TITLE)
        title.to_edge(UP, buff=0.3)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.4)

        sep = Line(UP * 2.8, DOWN * 3.6, color=GREY_C, stroke_width=1.5)
        self.play(Create(sep), run_time=0.4)

        # ---- LEFT: Down phase ----
        d_title = Text("Down Phase", font_size=28, color=ORANGE).move_to(LEFT * 3.5 + UP * 2.1)
        self.play(FadeIn(d_title), run_time=0.45)

        d_target = combo_node("C3").move_to(LEFT * 3.5 + UP * 1.1)
        d_feat   = feature_node("Draw Deck").move_to(LEFT * 3.5 + ORIGIN)
        d_prov   = combo_node("C2").move_to(LEFT * 3.5 + DOWN * 1.1)
        d_cards  = card_node("{D,C…}").move_to(LEFT * 3.5 + DOWN * 2.3)

        # DFS traversal direction: C3 needs DrawDeck (feature→combo edge reversed
        # for dependency), C2 produces DrawDeck (combo→feature), cards are ingredients
        # of combos (card→combo).  Show the "needs" arrows pointing from combo to
        # required feature, and "produces" from combo to feature (same direction,
        # different meaning shown by color).
        ea = narr(d_target, d_feat, color=ORANGE, stroke_width=2.5, tip_length=0.18)   # C3 needs DrawDeck
        eb = narr(d_prov, d_feat, color=GREEN_D, stroke_width=2.5, tip_length=0.18)    # C2 produces DrawDeck
        ec = narr(d_cards, d_prov, color=BLUE_D, stroke_width=2.5, tip_length=0.18)    # cards → C2

        d_start = Text("← start (target combo)", font_size=13, color=YELLOW).next_to(d_target, RIGHT, buff=0.1)
        d_leaf  = Text("← leaf (cards)",          font_size=13, color=YELLOW).next_to(d_cards,  RIGHT, buff=0.1)

        self.play(LaggedStart(
            Create(d_target), Create(ea), Create(d_feat), Create(eb), Create(d_prov),
            Create(ec), Create(d_cards), lag_ratio=0.22,
        ), run_time=2.4)
        self.play(FadeIn(d_start), FadeIn(d_leaf), run_time=0.4)
        d_dir = Text("▼ recurse down", font_size=19, color=ORANGE).move_to(LEFT * 3.5 + DOWN * 3.2)
        self.play(FadeIn(d_dir), run_time=0.4)
        self.wait(0.8)

        # ---- RIGHT: Up phase ----
        u_title = Text("Up Phase", font_size=28, color=GREEN_D).move_to(RIGHT * 3.5 + UP * 2.1)
        self.play(FadeIn(u_title), run_time=0.45)

        u_cards  = card_node("{A…D}").move_to(RIGHT * 3.5 + DOWN * 2.3)
        u_combos = combo_node("C1…C3").move_to(RIGHT * 3.5 + DOWN * 0.8)
        u_feats  = feature_node("Win  etc.").move_to(RIGHT * 3.5 + UP * 1.1)

        fa = narr(u_cards, u_combos, color=BLUE_D, stroke_width=2.5, tip_length=0.18)   # cards → combos
        fb = narr(u_combos, u_feats, color=GREEN_D, stroke_width=2.5, tip_length=0.18)  # combos → features

        u_start  = Text("← start",  font_size=15, color=YELLOW).next_to(u_cards,  LEFT, buff=0.1)
        u_result = Text("← result", font_size=15, color=YELLOW).next_to(u_feats,  LEFT, buff=0.1)

        self.play(LaggedStart(
            Create(u_cards), Create(fa), Create(u_combos), Create(fb), Create(u_feats),
            lag_ratio=0.24,
        ), run_time=2.0)
        self.play(FadeIn(u_start), FadeIn(u_result), run_time=0.4)
        u_dir = Text("▲ propagate up", font_size=19, color=GREEN_D).move_to(RIGHT * 3.5 + DOWN * 3.2)
        self.play(FadeIn(u_dir), run_time=0.4)
        self.wait(2.5)


# ---- Legacy aliases keep old render scripts working ----
class IntroAndRoadmap(Scene06_DownVsUp): pass
class GraphEncodingScene(Scene01_GraphOverview): pass
class DownPhaseSimple(Scene02_DownPhaseDFS): pass
class DownPhaseVariantSets(Scene03_VariantSetsGeometric): pass
class DownPhaseRedundancy(Scene04_MinimalSets): pass
class UpPhaseSimple(Scene05_UpPhase): pass
class UpPhaseComplex(Scene05_UpPhase): pass
class DownVsUpSideBySide(Scene06_DownVsUp): pass
class OptimizationEpilogue(Scene06_DownVsUp): pass
class QuickPreview(Scene01_GraphOverview): pass
