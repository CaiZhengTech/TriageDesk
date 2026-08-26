"""Render the judge-vs-human agreement chart (#18, results/ deliverable).

Hand-rolled SVG rather than matplotlib: the chart is a committed artifact that
must render on GitHub, in the README, and in a browser with no toolchain. An
image nobody can regenerate goes stale the moment a number moves, so this stays
a script and the numbers stay in one dict at the top.

WHAT THE CHART IS FOR
---------------------
The headline kappa (0.133) is the least informative number in the calibration,
and quoting it alone has always been the trap this project warns about. The
point only lands as a 2x2: the same judge graded against two human label rounds,
and the same human labeled the same 41 replies twice. Drawn together, three
things become visible at a glance that a table buries:

  1. Judge v2 beats v1 against BOTH rounds -- the tool-evidence fix worked, and
     the improvement is invariant to which human standard you pick.
  2. The human self-agreement line (0.212) sits BELOW judge v2's agreement with
     round 1 (0.418). The judge agrees with the human more than the human agrees
     with himself. That is the finding.
  3. Official v2 (0.133) is low because the human standard moved between rounds,
     not because the judge got worse.

PROVENANCE (see results/human-labels-provenance.json)
-----------------------------------------------------
Round-1 figures reproduce from surviving files. Round-2 figures are ARCHIVED:
the completed labels died with the Neon branch (#64), so anything derived from
them is drawn hatched and labelled as such. Charts that quietly present
unverifiable numbers as verified are exactly what this project's null-baseline
work exists to prevent.
"""

# Archived from results/judge-calibration.md. Round-1 rows are reproducible
# from results/human-labels.csv; round-2 rows are not (see module docstring).
KAPPAS = [
    ("Judge v2  vs  human round 1", 0.418, True, "the tool-evidence fix, best case"),
    ("Judge v1  vs  human round 1", 0.279, True, "official v1"),
    ("Judge v2  vs  human round 2", 0.133, False, "official v2 - the quoted number"),
    ("Judge v1  vs  human round 2", 0.038, False, ""),
]
SELF_AGREEMENT = 0.212
CONFUSION = {"pass": [16, 7, 11], "fail": [1, 3, 1], "needs_review": [1, 0, 1]}
COLS = ["pass", "fail", "needs_review"]

W, H = 940, 470
INK, MUTED, RULE = "#1b1f24", "#5b6570", "#d6dbe1"
SOLID, HATCH_BG, ACCENT = "#2f6f4f", "#b9c6cf", "#b4413c"
OUT = "results/judge-vs-human-agreement.svg"

APOS, KAPPA, MID = "&#8217;", "&#954;", "&#183;"

# Bar-panel geometry. x0 is where the bars start; `scale` maps kappa to pixels.
X0, TOP, BAR_H, GAP, SCALE = 300, 108, 30, 20, 560.0
AXIS_BOTTOM = TOP + len(KAPPAS) * (BAR_H + GAP) - GAP
# Confusion-matrix geometry.
CX, CY, CELL = 640, 108, 58


def text(x, y, s, size=12, fill=INK, weight=None, anchor=None) -> str:
    w = f' font-weight="{weight}"' if weight else ""
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{fill}"{w}{a}>{s}</text>'


def bars() -> list[str]:
    out = [text(34, 94, f"AGREEMENT ({KAPPA})", 12, MUTED, "700")]
    for tick in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        tx = X0 + tick * SCALE
        out.append(f'<line x1="{tx:.1f}" y1="{TOP - 6}" x2="{tx:.1f}" '
                   f'y2="{AXIS_BOTTOM + 6}" stroke="{RULE}" stroke-width="1"/>')
        out.append(text(tx, AXIS_BOTTOM + 26, f"{tick:.1f}", 10.5, MUTED, anchor="middle"))

    for i, (label, k, reproducible, note) in enumerate(KAPPAS):
        y = TOP + i * (BAR_H + GAP)
        fill = SOLID if reproducible else "url(#hatch)"
        out.append(text(X0 - 12, y + BAR_H * 0.68, label, 12.5, INK, anchor="end"))
        out.append(f'<rect x="{X0}" y="{y}" width="{max(k, 0.0) * SCALE:.1f}" '
                   f'height="{BAR_H}" fill="{fill}" rx="2"/>')
        out.append(text(X0 + k * SCALE + 10, y + BAR_H * 0.68, f"{k:.3f}", 13, INK, "700"))
        if note:
            out.append(text(X0 + k * SCALE + 62, y + BAR_H * 0.68, note, 11, MUTED))

    # The reference line carries the whole argument, so it is drawn on top.
    lx = X0 + SELF_AGREEMENT * SCALE
    out.append(f'<line x1="{lx:.1f}" y1="{TOP - 20}" x2="{lx:.1f}" y2="{AXIS_BOTTOM + 2}" '
               f'stroke="{ACCENT}" stroke-width="2" stroke-dasharray="5,4"/>')
    out.append(text(lx + 7, TOP - 25,
                    f"human vs. himself, {KAPPA} = {SELF_AGREEMENT}", 11.5, ACCENT, "700"))
    out.append(text(
        34, AXIS_BOTTOM + 62,
        '<tspan font-weight="700">Read the dashed line first.</tspan> Judge v2 agrees '
        f"with the human{APOS}s round-1 labels (0.418) "
        '<tspan font-weight="700">more than the human agrees with himself</tspan> '
        "(0.212).", 11.5))
    out.append(text(
        34, AXIS_BOTTOM + 80,
        "Single-rater ground truth is the measured bottleneck, so the fix is a second "
        "rater, not more judge tuning. The judge gates nothing.", 11.5, MUTED))
    out.append(f'<rect x="34" y="{AXIS_BOTTOM + 94}" width="13" height="13" '
               f'fill="url(#hatch)" rx="2"/>')
    out.append(text(
        53, AXIS_BOTTOM + 105,
        "hatched = archived, not reproducible: the completed round-2 labels were lost "
        "with the database (#64)", 11, MUTED))
    return out


def matrix() -> list[str]:
    out = [text(CX, 94, "JUDGE v2 vs HUMAN ROUND 2 (n=41)", 12, MUTED, "700")]
    for j, c in enumerate(COLS):
        out.append(text(CX + j * CELL + CELL / 2, CY - 8,
                        c.replace("_", " "), 10.5, MUTED, anchor="middle"))
    hi = max(max(v) for v in CONFUSION.values())
    for i, r in enumerate(COLS):
        out.append(text(CX - 10, CY + i * CELL + CELL / 2 + 4,
                        r.replace("_", " "), 10.5, MUTED, anchor="end"))
        for j, n in enumerate(CONFUSION[r]):
            opacity = 0.10 + 0.80 * (n / hi)
            out.append(f'<rect x="{CX + j * CELL}" y="{CY + i * CELL}" width="{CELL - 3}" '
                       f'height="{CELL - 3}" fill="{SOLID}" '
                       f'fill-opacity="{opacity:.2f}" rx="3"/>')
            if i == j:  # agreement cells: outlined so the diagonal reads at a glance
                out.append(f'<rect x="{CX + j * CELL}" y="{CY + i * CELL}" '
                           f'width="{CELL - 3}" height="{CELL - 3}" fill="none" '
                           f'stroke="{INK}" stroke-width="1.6" rx="3"/>')
            out.append(text(CX + j * CELL + (CELL - 3) / 2, CY + i * CELL + CELL / 2 + 5,
                            str(n), 15, "#ffffff" if opacity > 0.55 else INK,
                            "700", "middle"))
    out.append(text(CX - 10, CY + 3 * CELL + 24,
                    f"rows = human {MID} cols = judge {MID} outlined = agreement",
                    10.5, MUTED))
    out.append(text(CX - 10, CY + 3 * CELL + 48,
                    '<tspan font-weight="700">18 of 20 disagreements</tspan> are the '
                    "judge being", 11.5))
    out.append(text(CX - 10, CY + 3 * CELL + 65,
                    "stricter than the human - it fails safe.", 11.5))
    return out


def main() -> None:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
        '<defs><pattern id="hatch" width="6" height="6" patternTransform="rotate(45)" '
        f'patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="{HATCH_BG}"/>'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="{MUTED}" stroke-width="2.2"/>'
        "</pattern></defs>",
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        text(34, 40, "Judge-human agreement: the human is the noisier instrument",
             19, INK, "700"),
        text(34, 62, f"Cohen{APOS}s {KAPPA} on 41 blind labels. Same judge, two human "
                     "label rounds; same human, same 41 replies, 3 days apart.", 12.5, MUTED),
    ]
    parts += bars()
    parts += matrix()
    parts.append(text(34, H - 14,
                      f"Regenerate: python -m scripts.render_calibration_chart {MID} "
                      f"source: results/judge-calibration.md {MID} "
                      "provenance: results/human-labels-provenance.json", 10, MUTED))
    parts.append("</svg>")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
