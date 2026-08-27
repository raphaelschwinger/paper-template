#!/usr/bin/env python3
"""Figures as code: emit editable draw.io XML using the canonical styles in `drawio_styles.S`.

`DiagramBuilder` writes real `.drawio` files, so a diagram can be generated
from a script *and* still opened and nudged by hand afterwards — unlike a
rendered SVG, which is a dead end.

The two `build_*` functions below are worked examples carried over from an
earlier paper. Replace them with your own; keep the pattern:

    b = DiagramBuilder("my-figure", width, height)
    node = b.vertex("label", "box_blue", x, y, w, h, vid="node")
    b.edge(node, other)
    (FIGURES_DIR / "my-figure.drawio").write_text(b.build_xml())

Then export with `make drawio`. Commit both the `.drawio` and its exports.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

# Import canonical styles from the same package directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawio_styles import S

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _edge_style(
    *,
    dashed: bool = False,
    flow: bool = False,
    exit_x: float | None = None,
    exit_y: float | None = None,
    entry_x: float | None = None,
    entry_y: float | None = None,
) -> str:
    base = S["edge_dashed" if dashed else "edge"]
    style = (
        f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;{base}"
    )
    if flow:
        style += ";flowAnimation=1"
    if exit_x is not None:
        style += f";exitX={exit_x};exitDx=0"
    if exit_y is not None:
        style += f";exitY={exit_y};exitDy=0"
    if entry_x is not None:
        style += f";entryX={entry_x};entryDx=0"
    if entry_y is not None:
        style += f";entryY={entry_y};entryDy=0"
    return style


class DiagramBuilder:
    def __init__(self, name: str, page_width: int, page_height: int) -> None:
        self.name = name
        self.page_width = page_width
        self.page_height = page_height
        self._next_id = 2
        self.cells: list[str] = []

    def _id(self) -> str:
        cid = str(self._next_id)
        self._next_id += 1
        return cid

    def vertex(
        self,
        value: str,
        style_key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        vid: str | None = None,
    ) -> str:
        cid = vid or self._id()
        self.cells.append(
            f'    <mxCell id="{cid}" value="{_esc(value)}" '
            f'style="{_esc(S[style_key])}" vertex="1" parent="1">\n'
            f'      <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>\n'
            f"    </mxCell>"
        )
        return cid

    def edge(
        self,
        source: str,
        target: str,
        *,
        label: str = "",
        dashed: bool = False,
        flow: bool = False,
        exit_x: float | None = None,
        exit_y: float | None = None,
        entry_x: float | None = None,
        entry_y: float | None = None,
        points: list[tuple[int, int]] | None = None,
    ) -> str:
        cid = self._id()
        style = _edge_style(
            dashed=dashed,
            flow=flow,
            exit_x=exit_x,
            exit_y=exit_y,
            entry_x=entry_x,
            entry_y=entry_y,
        )
        geom = '      <mxGeometry relative="1" as="geometry"/>'
        if points:
            pts = "\n".join(f'          <mxPoint x="{px}" y="{py}"/>' for px, py in points)
            geom = (
                '      <mxGeometry relative="1" as="geometry">\n'
                '        <Array as="points">\n'
                f"{pts}\n"
                "        </Array>\n"
                "      </mxGeometry>"
            )
        label_attr = f' value="{_esc(label)}"' if label else ' value=""'
        self.cells.append(
            f'    <mxCell id="{cid}"{label_attr} style="{_esc(style)}" '
            f'edge="1" parent="1" source="{source}" target="{target}">\n'
            f"{geom}\n"
            f"    </mxCell>"
        )
        return cid

    def line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        label: str = "",
        dashed: bool = True,
    ) -> str:
        """Decorative line via edge between two invisible anchor points."""
        a = self.vertex("", "text", x1, y1, 1, 1)
        b = self.vertex("", "text", x2, y2, 1, 1)
        style = _edge_style(dashed=dashed)
        style = style.replace("endArrow=block;endFill=1;", "endArrow=none;")
        cid = self._id()
        self.cells.append(
            f'    <mxCell id="{cid}" value="{_esc(label)}" style="{_esc(style)}" '
            f'edge="1" parent="1" source="{a}" target="{b}">\n'
            f'      <mxGeometry relative="1" as="geometry"/>\n'
            f"    </mxCell>"
        )
        return cid

    def build_xml(self) -> str:
        body = "\n".join(self.cells)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="{_esc(self.name)}" id="{_esc(self.name)}">
    <mxGraphModel dx="900" dy="600" grid="1" gridSize="10" guides="1"
      tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1"
      pageWidth="{self.page_width}" pageHeight="{self.page_height}"
      math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
{body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def build_architecture_loop() -> str:
    b = DiagramBuilder("architecture-loop", 920, 340)

    a = b.vertex(
        "(a) Pretrained&#xa;video / JEPA",
        "box_purple",
        30,
        120,
        150,
        70,
        vid="a",
    )
    adapt = b.vertex(
        "(b) Sensor adaptation&#xa;camera / lidar / radar / GPS-IMU",
        "box_blue",
        260,
        110,
        170,
        90,
        vid="b",
    )
    wm = b.vertex(
        "(c) World model&#xa;latent + dynamics",
        "box",
        490,
        105,
        170,
        90,
        vid="c",
    )
    policy = b.vertex(
        "(d) Policy training&#xa;in imagination",
        "box_orange",
        730,
        30,
        160,
        70,
        vid="d",
    )
    probe = b.vertex(
        "(e) Display-probe&#xa;evaluation",
        "box_green",
        730,
        210,
        160,
        70,
        vid="e",
    )
    onwater = b.vertex(
        "(f) On-water runs",
        "box_red",
        360,
        250,
        140,
        60,
        vid="f",
    )
    memory = b.vertex(
        "(g) Episodic&#xa;memory",
        "box_purple",
        560,
        20,
        130,
        60,
        vid="g",
    )

    b.edge(a, adapt)
    b.edge(adapt, wm)
    b.edge(wm, policy, exit_x=1, exit_y=0.25, entry_x=0, entry_y=0.5, label="imagination")
    b.edge(wm, probe, exit_x=1, exit_y=0.75, entry_x=0, entry_y=0.5, label="operator display")
    b.edge(
        memory,
        policy,
        dashed=True,
        flow=True,
        label="novel episodes",
        exit_x=1,
        exit_y=0.5,
        entry_x=0,
        entry_y=0.25,
    )
    b.edge(
        onwater,
        adapt,
        flow=True,
        label="on-water data",
        exit_x=0.5,
        exit_y=0,
        entry_x=0.5,
        entry_y=1,
        points=[(430, 230)],
    )
    b.edge(
        onwater,
        wm,
        flow=True,
        exit_x=1,
        exit_y=0.25,
        entry_x=0.25,
        entry_y=1,
        points=[(520, 250)],
    )
    b.edge(
        memory,
        wm,
        dashed=True,
        flow=True,
        exit_x=0.5,
        exit_y=1,
        entry_x=0.75,
        entry_y=0,
        points=[(625, 95)],
    )

    return b.build_xml()


def build_policy_phases() -> str:
    b = DiagramBuilder("policy-phases", 840, 300)

    b.vertex(
        "Near-zero real-world exposure",
        "panel",
        30,
        40,
        360,
        170,
        vid="panel",
    )
    p1 = b.vertex(
        "Phase 1: Imitation&#xa;Data: human demonstrations&#xa;Safety: no added risk",
        "box_blue",
        50,
        90,
        150,
        100,
        vid="p1",
    )
    p2 = b.vertex(
        "Phase 2: RL in world model&#xa;Data: offline + imagination&#xa;Safety: no vessel exposure",
        "box_orange",
        220,
        90,
        150,
        100,
        vid="p2",
    )
    b.vertex(
        "Phase 3: On-water fine-tuning&#xa;Data: supervised test runs&#xa;Safety: correction under human control",
        "box_red",
        430,
        80,
        200,
        110,
        vid="p3",
    )

    b.line(450, 55, 620, 55, label="Human override", dashed=True)
    b.edge(p1, p2, exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.5)

    arrow_id = b._id()
    b.cells.append(
        f'    <mxCell id="{arrow_id}" value="" '
        f'style="endArrow=block;endFill=1;html=1;strokeColor=#000000;strokeWidth=2;'
        f'sketch=1;curveFitting=1;jiggle=2;fontFamily=Helvetica;fontSize=14;" '
        f'edge="1" parent="1">\n'
        f'      <mxGeometry relative="1" as="geometry">\n'
        f'        <mxPoint x="50" y="260" as="sourcePoint"/>\n'
        f'        <mxPoint x="810" y="260" as="targetPoint"/>\n'
        f"      </mxGeometry>\n"
        f"    </mxCell>"
    )
    b.vertex(
        "Real-world exposure / risk →",
        "text",
        310,
        230,
        240,
        30,
        vid="axis_lbl",
    )

    return b.build_xml()


def main() -> None:
    outputs = {
        "architecture-loop.drawio": build_architecture_loop(),
        "policy-phases.drawio": build_policy_phases(),
    }
    for name, xml in outputs.items():
        path = FIGURES_DIR / name
        path.write_text(xml, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
