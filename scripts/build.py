#!/usr/bin/env python3
"""Generate the Flatcap 2.0 CSS files for FreshRSS (User CSS extension).

    python3 scripts/build.py            # write flatcap*.css in the repo root
    python3 scripts/build.py --check    # fail if the generated files are stale
    python3 scripts/build.py --contrast # print token-level contrast of key pairs
    python3 scripts/build.py --sync     # refresh src/theme.json from ../00-Flatcap

Inputs : src/theme.json (vendored copy of the Flatcap 2.0 core, the only source
         of values) and src/rules.css (FreshRSS rules written against --fc-* roles).
Outputs: flatcap.css (Slate), flatcap-daylight.css, flatcap-system.css.

Python 3.10+, standard library only. Output is deterministic.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "src" / "theme.json"
RULES = ROOT / "src" / "rules.css"
UPSTREAM = (ROOT / ".." / "00-Flatcap" / "src" / "theme.json").resolve()

# role groups -------------------------------------------------------------
# Every semantic color role is exported (as --fc-*) except the categorical
# data.* series, which FreshRSS has no use for. contrast.* only feeds the
# prefers-contrast: more override.
CONTRAST_MAP = {
    "text.primary": "contrast.text.primary",
    "text.secondary": "contrast.text.secondary",
    "text.muted": "contrast.text.muted",
    "border.control": "contrast.border.control",
}
GOOGLE_FAMILIES = [  # (css2 family param, families named in theme.json)
    "IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400",
    "Cascadia+Code:wght@400;600",
    "Cascadia+Mono:wght@400",
]

# host adaptation: FreshRSS shows third-party favicons on a plate so that
# dark glyphs stay visible on Slate and light glyphs on Daylight.
FAVICON_PLATE = {"slate": "text.primary", "daylight": "bg.raised"}

OUTPUTS = {
    "flatcap.css": "slate",
    "flatcap-daylight.css": "daylight",
    "flatcap-system.css": "system",
}


def cssname(key: str) -> str:
    return "--fc-" + key.replace(".", "-")


def load() -> dict:
    return json.loads(THEME.read_text(encoding="utf-8"))


# color math --------------------------------------------------------------
def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def lum(h: str) -> float:
    def ch(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# CSS filter solver -------------------------------------------------------
# Icons in FreshRSS are <img> SVGs, so their color can only be changed with a
# CSS filter. Starting from black (brightness(0)), a chain of
# invert/sepia/saturate/hue-rotate/brightness/contrast is fitted to the target
# role color with SPSA. Seeded from the hex value: same input, same output.
def _clamp(v: float) -> float:
    return max(0.0, min(255.0, v))


class _Color:
    def __init__(self, r: float, g: float, b: float):
        self.r, self.g, self.b = r, g, b

    def _mul(self, m: list[float]) -> None:
        r, g, b = self.r, self.g, self.b
        self.r = _clamp(r * m[0] + g * m[1] + b * m[2])
        self.g = _clamp(r * m[3] + g * m[4] + b * m[5])
        self.b = _clamp(r * m[6] + g * m[7] + b * m[8])

    def hue_rotate(self, deg: float) -> None:
        a = math.radians(deg)
        s, c = math.sin(a), math.cos(a)
        self._mul([
            0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
            0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283,
            0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072,
        ])

    def sepia(self, v: float) -> None:
        k = 1 - v
        self._mul([
            0.393 + 0.607 * k, 0.769 - 0.769 * k, 0.189 - 0.189 * k,
            0.349 - 0.349 * k, 0.686 + 0.314 * k, 0.168 - 0.168 * k,
            0.272 - 0.272 * k, 0.534 - 0.534 * k, 0.131 + 0.869 * k,
        ])

    def saturate(self, v: float) -> None:
        self._mul([
            0.213 + 0.787 * v, 0.715 - 0.715 * v, 0.072 - 0.072 * v,
            0.213 - 0.213 * v, 0.715 + 0.285 * v, 0.072 - 0.072 * v,
            0.213 - 0.213 * v, 0.715 - 0.715 * v, 0.072 + 0.928 * v,
        ])

    def _linear(self, slope: float, icpt: float = 0.0) -> None:
        self.r = _clamp(self.r * slope + icpt * 255)
        self.g = _clamp(self.g * slope + icpt * 255)
        self.b = _clamp(self.b * slope + icpt * 255)

    def brightness(self, v: float) -> None:
        self._linear(v)

    def contrast(self, v: float) -> None:
        self._linear(v, -(0.5 * v) + 0.5)

    def invert(self, v: float) -> None:
        self.r = _clamp((v + self.r / 255 * (1 - 2 * v)) * 255)
        self.g = _clamp((v + self.g / 255 * (1 - 2 * v)) * 255)
        self.b = _clamp((v + self.b / 255 * (1 - 2 * v)) * 255)

    def hsl(self) -> tuple[float, float, float]:
        h, l, s = colorsys.rgb_to_hls(self.r / 255, self.g / 255, self.b / 255)
        return h * 100, s * 100, l * 100


def _apply(vals: list[float]) -> _Color:
    c = _Color(0, 0, 0)
    c.invert(vals[0] / 100)
    c.sepia(vals[1] / 100)
    c.saturate(vals[2] / 100)
    c.hue_rotate(vals[3] * 3.6)
    c.brightness(vals[4] / 100)
    c.contrast(vals[5] / 100)
    return c


def solve_filter(target_hex: str) -> tuple[str, float]:
    """Return (css filter chain, max per-channel error in 0-255 units)."""
    tr, tg, tb = rgb(target_hex)
    th, ts, tl = _Color(tr, tg, tb).hsl()
    rnd = random.Random(int(hashlib.sha256(target_hex.encode()).hexdigest()[:12], 16))

    def loss(v: list[float]) -> float:
        c = _apply(v)
        h, s, l = c.hsl()
        return (abs(c.r - tr) + abs(c.g - tg) + abs(c.b - tb)
                + abs(h - th) + abs(s - ts) + abs(l - tl))

    def fix(value: float, idx: int) -> float:
        mx = 7500 if idx == 2 else 200 if idx in (4, 5) else 100
        if idx == 3:
            return value % mx
        return max(0.0, min(mx, value))

    def spsa(A: float, a: list[float], c: float, values: list[float], iters: int):
        gamma, best, best_loss = 1 / 6, list(values), math.inf
        values = list(values)
        for k in range(iters):
            ck = c / (k + 1) ** gamma
            deltas = [1 if rnd.random() > 0.5 else -1 for _ in range(6)]
            hi = [v + ck * d for v, d in zip(values, deltas)]
            lo = [v - ck * d for v, d in zip(values, deltas)]
            diff = loss(hi) - loss(lo)
            for i in range(6):
                g = diff / (2 * ck) * deltas[i]
                values[i] = fix(values[i] - a[i] / (A + k + 1) * g, i)
            cur = loss(values)
            if cur < best_loss:
                best, best_loss = list(values), cur
        return best, best_loss

    best, best_loss = None, math.inf
    for _ in range(4):
        vals, l = spsa(5, [60, 180, 18000, 600, 1.2, 1.2], 15, [50, 20, 3750, 50, 100, 100], 1000)
        if l < best_loss:
            best, best_loss = vals, l
        if best_loss <= 5:
            break
    a1 = best_loss + 1
    best, best_loss = spsa(best_loss, [0.25 * a1, 0.25 * a1, a1, 0.25 * a1, 0.2 * a1, 0.2 * a1], 2, best, 600)
    c = _apply(best)
    err = max(abs(c.r - tr), abs(c.g - tg), abs(c.b - tb))
    v = [round(x) for x in best]
    chain = (f"brightness(0) saturate(100%) invert({v[0]}%) sepia({v[1]}%) saturate({v[2]}%) "
             f"hue-rotate({round(best[3] * 3.6)}deg) brightness({v[4]}%) contrast({v[5]}%)")
    return chain, err


# token emission ----------------------------------------------------------
def colors(theme: dict, mode: str, contrast: bool = False) -> dict[str, str]:
    t = dict(theme["themes"][mode])
    if contrast:
        for base, over in CONTRAST_MAP.items():
            t[base] = t[over]
    return t


def mode_vars(theme: dict, mode: str, contrast: bool = False) -> dict[str, str]:
    t = colors(theme, mode, contrast)
    out: dict[str, str] = {}
    for key, value in t.items():
        if key.startswith(("data.", "contrast.")):
            continue
        out[cssname(key)] = value
    shadow = theme["elevation"][mode]["shadow.overlay"]
    out["--fc-shadow-overlay"] = shadow
    out["--fc-shadow-color"] = re.search(r"(rgb\([^)]*\))\s*$", shadow).group(1)
    out["--fc-color-scheme"] = "dark" if mode == "slate" else "light"
    out["--fc-favicon-plate"] = t[FAVICON_PLATE[mode]]
    # scrim: the canvas color at reduced opacity (a dimmer, not a text surface)
    out["--fc-scrim"] = f"color-mix(in srgb, {t['bg.canvas']} 72%, transparent)"
    for name, role in (("icon", "text.secondary"), ("icon-hover", "text.primary"),
                       ("icon-accent", "accent.fg"), ("icon-on-accent", "accent.on"),
                       ("icon-danger", "danger.fg")):
        out[f"--fc-filter-{name}"] = solve_filter(t[role])[0]
    return out


def foundation_vars(theme: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in theme["typography"].items():
        out[cssname(key)] = value
    for key, value in theme["metrics"].items():
        out[cssname(key)] = value
    for key, value in theme["density"]["comfortable"].items():
        out[cssname(key)] = value
    return out


def block(selector: str, decls: dict[str, str], indent: str = "") -> str:
    body = "".join(f"{indent}\t{k}: {v};\n" for k, v in decls.items())
    return f"{indent}{selector} {{\n{body}{indent}}}\n"


def diff(base: dict[str, str], other: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in other.items() if base.get(k) != v}


def fonts_import() -> str:
    q = "&".join(f"family={f}" for f in GOOGLE_FAMILIES)
    return f"@import url('https://fonts.googleapis.com/css2?{q}&display=swap');\n"


def header(theme: dict, label: str, how: str) -> str:
    digest = hashlib.sha256(THEME.read_bytes()).hexdigest()[:12]
    return (
        f"/*******************************************************************\n"
        f" * Flatcap {theme['version']} for FreshRSS: {label}\n"
        f" * Quiet precision. The interface organizes. Content takes the\n"
        f" * foreground. Color informs.\n"
        f" *\n"
        f" * Core:   https://github.com/cheycron/flat-cap-theme\n"
        f" * Values: src/theme.json (Flatcap {theme['version']}, sha256 {digest}).\n"
        f" *         Every color, font, size and metric below comes from that\n"
        f" *         file through scripts/build.py. Do not edit by hand.\n"
        f" * Host:   FreshRSS 1.30, base theme \"Nord\", User CSS extension.\n"
        f" * Use:    {how}\n"
        f" * Fonts:  IBM Plex Sans (UI + reading), Cascadia Code (code).\n"
        f" *         The @import below is blocked by FreshRSS's default CSP\n"
        f" *         unless the instance relaxes it; install the fonts locally\n"
        f" *         or see README.md. Fallbacks are part of the stack.\n"
        f" *******************************************************************/\n"
    )


def build(theme: dict, which: str) -> str:
    rules = RULES.read_text(encoding="utf-8")
    found = foundation_vars(theme)
    parts = ['@charset "UTF-8";\n\n']
    if which == "slate":
        parts.append(header(theme, "Slate (dark)", "paste into Configuration > Extensions > User CSS."))
    elif which == "daylight":
        parts.append(header(theme, "Daylight (light)", "paste into Configuration > Extensions > User CSS."))
    else:
        parts.append(header(theme, "System (Slate, or Daylight when the OS prefers light)",
                            "paste into Configuration > Extensions > User CSS."))
    parts.append("\n" + fonts_import() + "\n")

    def tokens(mode: str) -> tuple[dict, dict]:
        return mode_vars(theme, mode), mode_vars(theme, mode, contrast=True)

    if which in ("slate", "daylight"):
        std, more = tokens(which)
        parts.append(block(":root", {**found, **std}))
        parts.append("\n@media (prefers-contrast: more) {\n")
        parts.append(block(":root", diff(std, more), "\t"))
        parts.append("}\n")
    else:
        s_std, s_more = tokens("slate")
        d_std, d_more = tokens("daylight")
        parts.append(block(":root", {**found, **s_std}))
        parts.append("\n@media (prefers-contrast: more) {\n")
        parts.append(block(":root", diff(s_std, s_more), "\t"))
        parts.append("}\n\n@media (prefers-color-scheme: light) {\n")
        parts.append(block(":root", diff(s_std, d_std), "\t"))
        parts.append("}\n\n@media (prefers-color-scheme: light) and (prefers-contrast: more) {\n")
        parts.append(block(":root", diff(s_std, d_more), "\t"))
        parts.append("}\n")
    parts.append("\n" + rules.rstrip() + "\n")
    return "".join(parts)


def contrast_report(theme: dict) -> str:
    pairs = [
        ("text.primary", "bg.canvas", 7), ("text.primary", "bg.surface", 7),
        ("text.primary", "bg.raised", 7), ("text.primary", "bg.hover", 7), ("text.primary", "bg.selected", 7),
        ("text.secondary", "bg.surface", 5), ("text.secondary", "bg.hover", 5),
        ("text.muted", "bg.canvas", 5), ("text.muted", "bg.surface", 5), ("text.muted", "bg.selected", 5),
        ("accent.fg", "bg.canvas", 5), ("accent.fg", "bg.surface", 5), ("accent.fg", "bg.raised", 5),
        ("accent.fg", "bg.selected", 5),
        ("accent.on", "accent.fill", 4.5), ("accent.on", "accent.hover", 4.5), ("accent.on", "accent.pressed", 4.5),
        ("accent.fill", "bg.canvas", 3), ("accent.fill", "bg.surface", 3),
        ("border.control", "bg.canvas", 3), ("border.control", "bg.surface", 3), ("border.control", "bg.raised", 3),
        ("focus.ring", "bg.canvas", 3), ("focus.ring", "bg.surface", 3), ("focus.ring", "bg.selected", 3),
        ("success.fg", "success.bg", 4.5), ("warning.fg", "warning.bg", 4.5),
        ("danger.fg", "danger.bg", 4.5), ("info.fg", "info.bg", 4.5),
        ("selection.fg", "selection.bg", 4.5),
        ("syntax.keyword", "bg.canvas", 5), ("syntax.function", "bg.canvas", 5), ("syntax.string", "bg.canvas", 5),
        ("syntax.number", "bg.canvas", 5), ("syntax.type", "bg.canvas", 5), ("syntax.comment", "bg.canvas", 5),
    ]
    lines = []
    for mode in ("slate", "daylight"):
        t = theme["themes"][mode]
        lines.append(f"[{mode}]")
        for fg, bg, target in pairs:
            r = ratio(t[fg], t[bg])
            lines.append(f"  {fg:<16} on {bg:<14} {r:6.2f}:1  target {target}:1  {'ok' if r >= target else 'FAIL'}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if generated files differ from a fresh build")
    ap.add_argument("--contrast", action="store_true", help="print token-level contrast ratios and exit")
    ap.add_argument("--sync", nargs="?", const=str(UPSTREAM), metavar="PATH",
                    help="copy theme.json from the core checkout (default ../00-Flatcap/src/theme.json)")
    args = ap.parse_args()

    if args.sync:
        src = Path(args.sync)
        if not src.is_file():
            print(f"error: {src} not found", file=sys.stderr)
            return 2
        shutil.copyfile(src, THEME)
        print(f"synced {src} -> {THEME.relative_to(ROOT)}")

    theme = load()
    if not str(theme.get("version", "")).startswith("2."):
        print(f"error: expected Flatcap 2.x theme.json, got {theme.get('version')}", file=sys.stderr)
        return 2
    if args.contrast:
        print(contrast_report(theme))
        return 0

    stale = []
    for name, which in OUTPUTS.items():
        text = build(theme, which)
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {name} ({len(text.encode())} bytes)")
    if args.check:
        if stale:
            print("stale: " + ", ".join(stale) + " (run python3 scripts/build.py)", file=sys.stderr)
            return 1
        print("ok: generated files are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
