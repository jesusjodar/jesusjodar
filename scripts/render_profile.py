#!/usr/bin/env python3
"""Render self-contained, font-independent profile assets. No external SVG resources."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
FONTS = {
    "heading": TTFont(OUT / "fonts/BarlowCondensed-Black.ttf"),
    "body": TTFont(OUT / "fonts/SpaceGrotesk.ttf"),
}
GLYPHS = {key: font.getGlyphSet(location={"wght": 500} if key == "body" else None) for key, font in FONTS.items()}
CMAPS = {key: font.getBestCmap() for key, font in FONTS.items()}
SUBTITLE = "Desarrollo, investigación y diseño de interfaces de nueva generación"
MONTHS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


class SVG:
    def __init__(self, width: int, height: int, title: str, description: str = ""):
        self.width, self.height = width, height
        self.title, self.description = title, description
        self.parts = [f'<rect width="{width}" height="{height}" fill="#000000"/>']
        self.defs = {}

    def raw(self, value: str):
        self.parts.append(value)

    def text(self, value: str, x: float, y: float, size=28, font="body", opacity=1, max_width=None):
        """Position a baseline; trace glyphs so GitHub does not substitute the font."""
        face = FONTS[font]
        scale = size / face["head"].unitsPerEm
        width = sum(GLYPHS[font][CMAPS[font].get(ord(c), ".notdef")].width for c in value) * scale
        if max_width and width > max_width:
            scale *= max_width / width
            width = max_width
        uses, advance = [], 0
        for c in value:
            name = CMAPS[font].get(ord(c), ".notdef")
            key = f"{font}-{ord(c)}"
            if key not in self.defs:
                pen = SVGPathPen(GLYPHS[font])
                GLYPHS[font][name].draw(pen)
                self.defs[key] = f'<path id="{key}" d="{pen.getCommands()}"/>'
            uses.append(f'<use href="#{key}" x="{advance}"/>')
            advance += GLYPHS[font][name].width
        self.raw(f'<g fill="#ffffff" opacity="{opacity}" transform="translate({x} {y}) scale({scale:.6f} {-scale:.6f})">{"".join(uses)}</g>')
        return width

    def line(self, x1, y1, x2, y2, opacity=.24):
        self.raw(f'<path d="M{x1} {y1}H{x2}" stroke="#ffffff" opacity="{opacity}"/>' if y1 == y2 else
                 f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#ffffff" opacity="{opacity}"/>')

    def save(self, name):
        mobile = "-mobile" in name
        # Space belongs inside the opaque panel, not in GitHub's outer gutters.
        padding = (16 if mobile else 24) if name.startswith("social-") else (32 if mobile else 48)
        height = self.height + padding*2
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}" '
            f'viewBox="0 0 {self.width} {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.description)}</desc>'
            f'<defs>{"".join(self.defs.values())}</defs>'
            f'<rect width="{self.width}" height="{height}" fill="#000000"/>'
            f'<g transform="translate(0 {padding})">{"".join(self.parts)}</g></svg>\n', encoding="utf-8")


def abstract(s: SVG, mobile=False, ribbon=False):
    """Layered white geometry, real Gaussian blur, black-to-transparent linear mask."""
    w, h = s.width, s.height
    s.raw('<defs><filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>'
          '<filter id="haze" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>'
          '<linearGradient id="fade"><stop offset="0" stop-color="#000000"/><stop offset=".46" stop-color="#000000" stop-opacity=".97"/>'
          '<stop offset="1" stop-color="#000000" stop-opacity="0"/></linearGradient></defs>')
    cx, cy = (.92*w, .46*h) if mobile else (.82*w, .48*h)
    s.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{w*.20}" ry="{h*.26}" fill="#ffffff" opacity=".08" filter="url(#haze)"/>')
    if ribbon:
        for i in range(20):
            x = w*.53 + i*w*.027
            s.raw(f'<path d="M{x} {-h*.2}C{x-170} {h*.4} {x+230} {h*.5} {x-30} {h*1.3}" fill="none" stroke="#ffffff" stroke-width="2.5" opacity=".5" filter="url(#soft)"/>')
    else:
        s.raw(f'<g transform="rotate(-27 {cx} {cy})" fill="none" stroke="#ffffff">')
        for i in range(23):
            rx = w*.10+i*w*.009
            s.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{rx*.72}" stroke-width="{1.5+(i%3)*.7}" opacity="{.12+(i%5)*.07}" filter="url(#soft)"/>')
        s.raw('</g>')
    s.raw(f'<rect width="{w}" height="{h}" fill="url(#fade)"/>')


def hero(mobile=False):
    w, h, pad = (600, 720, 38) if mobile else (1200, 730, 70)
    s = SVG(w, h, "Jesús Jódar", SUBTITLE)
    abstract(s, mobile)
    s.text("@jesusjodar / software · IA · diseño", pad, 55, 20 if mobile else 21, max_width=w-2*pad)
    s.line(pad, 78, w-pad, 78)
    if mobile:
        s.text("JESÚS", pad-3, 280, 210, "heading", max_width=w-2*pad)
        s.text("JÓDAR.", pad-3, 478, 210, "heading", max_width=w-2*pad)
        for line, y in zip(["Desarrollo, investigación", "y diseño de interfaces", "de nueva generación"], [558, 598, 638]):
            s.text(line, pad, y, 30, max_width=w-2*pad)
    else:
        s.text("JESÚS", pad-3, 325, 270, "heading")
        s.text("JÓDAR.", pad-3, 562, 270, "heading")
        s.text("Desarrollo, investigación y diseño", pad, 636, 33)
        s.text("de interfaces de nueva generación", pad, 682, 33)
    s.save("hero-mobile.svg" if mobile else "hero.svg")


def about(mobile=False):
    w, pad = (600, 38) if mobile else (1200, 70)
    s = SVG(w, 640 if mobile else 410, "Sobre mí", "Desarrollo de software, IA local, automatización, diseño 3D e interfaces expresivas.")
    s.line(pad, 20, w-pad, 20)
    s.text("SOBRE MÍ.", pad, 102, 67, "heading")
    lines = (["Combino desarrollo de software,", "automatización y diseño 3D para", "convertir ideas en experiencias.", "Me interesan los agentes con", "memoria y herramientas, los modelos", "locales, las interfaces expresivas", "y las tecnologías emergentes."] if mobile else
             ["Combino desarrollo de software, automatización y diseño 3D", "para convertir ideas en experiencias. Me interesan los agentes", "con memoria y herramientas, los modelos locales, las interfaces", "expresivas y las tecnologías emergentes."])
    for i, line in enumerate(lines):
        s.text(line, pad, 161+i*42, 28 if mobile else 29, max_width=w-2*pad)
    tags = ["IA LOCAL  /  AGENTES  /  INTERFACES", "APPLE  /  BLENDER  /  VIDEOJUEGOS"]
    for i, line in enumerate(tags):
        s.text(line, pad, (526 if mobile else 332)+i*34, 21, max_width=w-2*pad)
    s.save("about-mobile.svg" if mobile else "about.svg")


def project(mobile=False):
    w, pad = (600, 38) if mobile else (1200, 70)
    h = 275 if mobile else 215
    s = SVG(w, h, "PORTFOLIO", "Portfolio personal interactivo")
    inset = pad
    s.text("01 / IDENTIDAD DIGITAL", inset, 56, 20, max_width=w-2*inset)
    s.text("PORTFOLIO", inset-2, 132, 90, "heading", max_width=w-2*inset-30)
    for i, line in enumerate(["Mi espacio de diseño, desarrollo", "e ideas en la web."] if mobile else ["Mi espacio de diseño, desarrollo e ideas en la web."]):
        s.text(line, inset, 190+i*36, 26, max_width=w-2*inset)
    x, y = w-pad-42, 40
    s.raw(f'<path d="M{x-14} {y+14}l18-18m-18 0h18v18" fill="none" stroke="#ffffff" stroke-width="3"/>')
    s.save(f"portfolio{'-mobile' if mobile else ''}.svg")


def socials(mobile=False):
    # Equal-height image segments form one black strip, while each link stays clickable.
    # 5% leading space + four 15% buttons + 35% trailing space = 100%.
    # An inner 10px / 8px offset aligns the first icon with each panel's text.
    width, height, button = (90, 144, 54) if mobile else (180, 144, 64)
    suffix = "-mobile" if mobile else ""
    icons = json.loads((ROOT/"data/social-icons.json").read_text())
    for name, markup in icons.items():
        s = SVG(width, height, name)
        x, y = (8 if mobile else 10), (height-button)/2
        s.raw(f'<g transform="translate({x} {y}) scale({button/64})">'
              '<rect x="1" y="1" width="62" height="62" fill="none" stroke="#ffffff" stroke-width="2"/>'
              f'{markup}</g>')
        s.save(f"social-{name}{suffix}.svg")
    SVG(30 if mobile else 60, height, "").save(f"social-spacer-left{suffix}.svg")
    SVG(210 if mobile else 420, height, "").save(f"social-spacer-right{suffix}.svg")


def short_date(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return f"{d.day:02} {MONTHS[d.month-1]}"


def fit_lines(value, max_chars):
    words, lines, current = value.split(), [], ""
    for word in words:
        if current and len(current)+1+len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = (current+" "+word).strip()
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines[1] = lines[1].rstrip(". ") + "…"
    return lines[:2]


def activity_window(data):
    """Fourteen calendar days, including the snapshot day in Spain."""
    zone = ZoneInfo("Europe/Madrid")
    end = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")).astimezone(zone).date()
    start = end - timedelta(days=13)
    calendar = data.get("calendar") or {}
    days = sorted((day for week in calendar.get("weeks", []) for day in week["contributionDays"]
                   if start.isoformat() <= day["date"] <= end.isoformat()), key=lambda day: day["date"])
    commits = [commit for commit in data.get("commits", [])
               if start <= datetime.fromisoformat(commit["date"].replace("Z", "+00:00")).astimezone(zone).date() <= end]
    return start, end, days, commits[:3]


def activity(data, mobile=False):
    start, end, days, commits = activity_window(data)
    w, pad = (600, 38) if mobile else (1200, 70)
    calendar_height = 155
    row_height = 128 if mobile else 106
    height = 180 + (calendar_height if days else 0) + len(commits)*row_height + 80
    period = f"{start:%d/%m} – {end:%d/%m}"
    s = SVG(w, height, "Actividad en GitHub · últimas 2 semanas", "Contribuciones visibles y cambios en proyectos públicos del "+period+". Datos consultados: "+data["updated_at"])
    s.line(pad, 20, w-pad, 20)
    s.text("ACTIVIDAD.", pad, 108, 80, "heading")
    y = 155
    if days:
        total = sum(day["contributionCount"] for day in days)
        s.text(f"{total:,}".replace(",", ".")+" contribuciones visibles", pad, y, 30)
        s.text("Últimas 2 semanas · "+period, pad, y+36, 22, max_width=w-2*pad)
        # Two rows of seven days keep the original compact pixel treatment.
        columns = 7
        cell = 24 if mobile else 22
        gap = 5
        grid_y = y+76
        peak = max((day["contributionCount"] for day in days), default=1) or 1
        for i, day in enumerate(days):
            count = day["contributionCount"]
            opacity = .09 if not count else .18+.82*(count/peak)**.5
            x, top = pad+(i%columns)*(cell+gap), grid_y+(i//columns)*(cell+gap)
            label = f'{day["date"]}: {count} contribuciones'
            s.raw(f'<rect x="{x}" y="{top}" width="{cell}" height="{cell}" fill="#ffffff" fill-opacity="{opacity:.3f}"><title>{label}</title></rect>')
        y += calendar_height
    s.text("CAMBIOS EN ESTAS 2 SEMANAS", pad, y+20, 21, max_width=w-2*pad)
    y += 48
    for commit in commits:
        s.line(pad, y, w-pad, y)
        s.text(short_date(commit["date"]), pad, y+34, 20)
        x = pad+105
        s.text(commit["repo"].split("/")[-1], x, y+34, 27)
        for i, line in enumerate(fit_lines(commit["message"], 29 if mobile else 67)):
            s.text(line, x, y+67+i*29, 22, max_width=w-pad-x)
        y += row_height
    stamp = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
    s.text("Datos de GitHub · "+stamp, pad, height-29, 20)
    s.save("activity-mobile.svg" if mobile else "activity.svg")


def render(data):
    for mobile in (False, True):
        hero(mobile)
        about(mobile)
        project(mobile)
        socials(mobile)
        activity(data, mobile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT/"data/activity.json")
    args = parser.parse_args()
    render(json.loads(args.data.read_text(encoding="utf-8")))
