"""Canonical draw.io component styles for paper figures.

Ported from the Introduction-to-Deep-Reinforcement-Learning repo so that
diagrams share one visual language. See ``theme-drawio-svg.py`` for SVG
normalization after export.

Authoring rules:
- black (#000000) strokes/text on white/transparent fills by default;
- saturated colors only as *stroke* accents, never as heavy fills behind
  same-hue text;
- ``fontFamily=Helvetica`` and ``fontSize=14`` minimum on every label;
- ``sketch=1;curveFitting=1;jiggle=2`` for the hand-drawn look;
- never draw a full-page white background rectangle.
"""

SKETCH = "sketch=1;curveFitting=1;jiggle=2"
FONT = "fontFamily=Helvetica;fontSize=14"
BASE = f"whiteSpace=wrap;html=1;{SKETCH};{FONT}"
TEXT = (
    f"text;html=1;strokeColor=none;fillColor=none;align=center;"
    f"verticalAlign=middle;{SKETCH};{FONT};fontColor=#666666;fontStyle=2"
)

# Accent stroke colors (chosen to survive `invert(1) hue-rotate(180deg)`).
BLUE = "#6c8ebf"
GREEN = "#82b366"
ORANGE = "#d79b00"
RED = "#b85450"
PURPLE = "#9673a6"
GREY = "#666666"

S = {
    # Generic boxes — white/transparent fill, colored stroke as the accent.
    "box": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=2",
    "box_blue": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor={BLUE};strokeWidth=2",
    "box_green": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor={GREEN};strokeWidth=2",
    "box_orange": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor={ORANGE};strokeWidth=2",
    "box_red": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor={RED};strokeWidth=2",
    "box_purple": f"rounded=1;{BASE};fillColor=#FFFFFF;strokeColor={PURPLE};strokeWidth=2",
    # Sharp-corner rectangle (processes / data blocks).
    "rect": f"rounded=0;{BASE};fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=2",
    "rect_blue": f"rounded=0;{BASE};fillColor=#FFFFFF;strokeColor={BLUE};strokeWidth=2",
    "rect_green": f"rounded=0;{BASE};fillColor=#FFFFFF;strokeColor={GREEN};strokeWidth=2",
    "rect_orange": f"rounded=0;{BASE};fillColor=#FFFFFF;strokeColor={ORANGE};strokeWidth=2",
    "rect_purple": f"rounded=0;{BASE};fillColor=#FFFFFF;strokeColor={PURPLE};strokeWidth=2",
    # Ellipses (nodes / actors).
    "ellipse": f"ellipse;{BASE};fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=2",
    "ellipse_blue": f"ellipse;{BASE};fillColor=#FFFFFF;strokeColor={BLUE};strokeWidth=2",
    "ellipse_green": f"ellipse;{BASE};fillColor=#FFFFFF;strokeColor={GREEN};strokeWidth=2",
    "ellipse_red": f"ellipse;{BASE};fillColor=#FFFFFF;strokeColor={RED};strokeWidth=2",
    # Containers / panels (dashed, transparent).
    "panel": (
        f"rounded=1;{BASE};fillColor=none;strokeColor={GREY};strokeWidth=2;"
        "dashed=1;verticalAlign=top;fontStyle=1"
    ),
    "swimlane": (
        f"swimlane;startSize=28;fillColor=none;strokeColor={GREY};strokeWidth=2;"
        f"{SKETCH};{FONT};fontStyle=1"
    ),
    # Edges + labels.
    "edge": (
        f"endArrow=block;endFill=1;html=1;strokeColor=#000000;strokeWidth=1.5;{SKETCH};{FONT}"
    ),
    "edge_dashed": (
        f"endArrow=block;endFill=1;html=1;strokeColor=#000000;strokeWidth=1.5;"
        f"dashed=1;{SKETCH};{FONT}"
    ),
    "edge_label": f"{SKETCH};{FONT}",
    "text": TEXT,
}
