#!/usr/bin/env python3
"""Render self-contained, font-independent profile assets. No external SVG resources."""
from __future__ import annotations

import argparse
import base64
import io
from PIL import Image
import xml.etree.ElementTree as ET
import json
import math
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from cairosvg import svg2png
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
FONTS = {
    "heading": TTFont(OUT / "fonts/RobotoFlex-Heading.ttf"),
    "subtitle": TTFont(OUT / "fonts/RobotoFlex-Subtitle.ttf"),
    "body": TTFont(OUT / "fonts/RobotoFlex-Body.ttf"),
}
GLYPHS = {key: font.getGlyphSet(location={"wght": 500} if key == "body" else None) for key, font in FONTS.items()}
CMAPS = {key: font.getBestCmap() for key, font in FONTS.items()}
SUBTITLE = "Development, research and next-generation interface design"
MONTHS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def bayer_band(width, outgoing, incoming):
    """Static 4px / 4x4 Bayer sweep matching the portfolio's Paper shader."""
    height, pixel = 64, 4
    matrix = [0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5]
    def surface(hue, prefix):
        if hue is None:
            return f'<rect width="{width}" height="{height}" fill="#000"/>'
        root = ET.fromstring((OUT/"website/neon-noise.svg").read_text())
        root.set("width",str(width)); root.set("height",str(height))
        root.set("preserveAspectRatio","xMidYMid slice")
        ids = [node.attrib["id"] for node in root.iter() if "id" in node.attrib]
        markup = ET.tostring(root,encoding="unicode")
        for id in ids:
            markup = markup.replace(f'id="{id}"',f'id="{prefix}-{id}"').replace(f'url(#{id})',f'url(#{prefix}-{id})')
        return f'<defs><filter id="{prefix}-hue" color-interpolation-filters="sRGB"><feColorMatrix type="hueRotate" values="{hue}"/></filter></defs><g filter="url(#{prefix}-hue)">{markup}</g><rect width="{width}" height="{height}" fill="#000" opacity=".22"/>'
    cells=[]
    for y in range(0,height,pixel):
        for x in range(0,width,pixel):
            progress = (y+pixel/2)/height + .04*math.sin(x/width*math.tau)
            threshold = (matrix[(y//pixel%4)*4+x//pixel%4]+.5)/16
            if progress >= threshold:
                cells.append(f'M{x} {y}h{pixel}v{pixel}h-{pixel}z')
    return f'<defs><clipPath id="bayer-in"><path d="{"".join(cells)}" shape-rendering="crispEdges"/></clipPath></defs>'+surface(outgoing,"bayer-from")+'<g clip-path="url(#bayer-in)">'+surface(incoming,"bayer-to")+'</g>'


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

    def fitted(self, value, x, y, width, height):
        """Match the portfolio: fit actual glyph bounds on both axes."""
        glyphs = GLYPHS["heading"]
        bounds, advance = [], 0
        for c in value:
            glyph = glyphs[CMAPS["heading"].get(ord(c), ".notdef")]
            pen = BoundsPen(glyphs)
            glyph.draw(pen)
            if pen.bounds:
                a,b,cx,d = pen.bounds
                bounds.append((a+advance,b,cx+advance,d))
            advance += glyph.width
        left=min(b[0] for b in bounds); bottom=min(b[1] for b in bounds)
        right=max(b[2] for b in bounds); top=max(b[3] for b in bounds)
        self.text(value, 0, 0, FONTS["heading"]["head"].unitsPerEm, "heading")
        markup=self.parts.pop()
        sx=width/(right-left); sy=height/(top-bottom)
        self.raw(f'<g transform="translate({x-left*sx} {y+top*sy}) scale({sx} {sy})">{markup}</g>')

    def line(self, x1, y1, x2, y2, opacity=.24):
        self.raw(f'<path d="M{x1} {y1}H{x2}" stroke="#ffffff" opacity="{opacity}"/>' if y1 == y2 else
                 f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#ffffff" opacity="{opacity}"/>')

    def save(self, name):
        mobile = "-mobile" in name
        # Space belongs inside the opaque panel, not in GitHub's outer gutters.
        padding = 8 if name.startswith("social-") else 0
        transition = None
        base = name.replace("-mobile", "")
        if base == "about.svg": transition = (None, 200)
        elif base == "portfolio.svg": transition = (200, 100)
        elif base == "activity.svg": transition = (100, None)
        top_band = 63 if transition else 0
        bottom_band = 63 if base == "hero.svg" else 0
        band = bayer_band(self.width, *transition) if transition else ""
        ending = f'<g transform="translate(0 {self.height-1})">{bayer_band(self.width, 0, None)}</g>' if bottom_band else ""
        height = self.height + padding*2 + top_band + bottom_band
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}" '
            f'viewBox="0 0 {self.width} {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.description)}</desc>'
            f'<defs>{"".join(self.defs.values())}</defs>'
            f'<rect width="{self.width}" height="{height}" fill="#000000"/>'
            f'{band}<defs><clipPath id="panel-clip"><rect width="{self.width}" height="{self.height}"/></clipPath></defs><g transform="translate(0 {padding+top_band})" clip-path="url(#panel-clip)">{"".join(self.parts)}</g>{ending}</svg>\n', encoding="utf-8")
        if name.startswith("social-"):
            # Opaque raster edges avoid SVG viewport seams at fractional CSS widths.
            # Keep the editable SVG and regenerate its 3x PNG in every refresh.
            svg2png(url=str(OUT/name), write_to=str((OUT/name).with_suffix(".png")),
                    output_width=self.width*3, output_height=height*3,
                    background_color="#000000")


def abstract(s: SVG, mobile=False, ribbon=False, hue=0):
    """Use the portfolio's real noise artwork and Vitruvian figure."""
    background = ET.fromstring((OUT / "website/neon-noise.svg").read_text())
    background.set("width", str(s.width))
    background.set("height", str(s.height))
    background.set("preserveAspectRatio", "xMidYMid slice")
    s.raw(f'<defs><filter id="section-hue" color-interpolation-filters="sRGB"><feColorMatrix type="hueRotate" values="{hue}"/></filter></defs>')
    s.raw('<g filter="url(#section-hue)">'+ET.tostring(background, encoding="unicode")+'</g>')
    s.raw(f'<rect width="{s.width}" height="{s.height}" fill="#000" opacity=".22"/>')
    if not ribbon:
        figure = ET.fromstring((OUT / "website/side-artwork.svg").read_text())
        figure.set("preserveAspectRatio", "xMinYMin meet")
        figure.set("x", str(s.width * (.28 if mobile else .43)))
        figure.set("y", str(s.height * .16))
        figure.set("width", str(s.width * 1.35))
        figure.set("height", str(s.height * 2.0))
        s.raw('<defs><filter id="white-art"><feMorphology operator="dilate" radius="0.25"/><feColorMatrix values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 1 0"/></filter></defs>')
        s.raw(f'<defs><clipPath id="figure-clip"><rect width="{s.width}" height="{470 if mobile else 490}"/></clipPath></defs>')
        fade_start = s.width * (.52 if mobile else .52)
        fade_end = s.width * (.94 if mobile else .78)
        s.raw(f'<defs><linearGradient id="figure-fade" gradientUnits="userSpaceOnUse" x1="{fade_start}" y1="0" x2="{fade_end}" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient><mask id="figure-text-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{s.width}" height="{s.height}"><rect width="{s.width}" height="{s.height}" fill="url(#figure-fade)"/></mask></defs>')
        s.raw('<g clip-path="url(#figure-clip)" mask="url(#figure-text-mask)"><g filter="url(#white-art)">'+ET.tostring(figure, encoding="unicode")+'</g></g>')


def hero(mobile=False):
    w, h, pad = (600, 465, 35) if mobile else (1200, 465, 35)
    s = SVG(w, h, "Jesus Jodar", SUBTITLE)
    abstract(s, mobile)
    title_width = w-2*pad if mobile else 820
    s.fitted("JESUS", pad, 35, title_width, 190)
    s.fitted("JODAR.", pad, 240, title_width, 190)
    s.save("hero-mobile.svg" if mobile else "hero.svg")


ABOUT_TEXT = (
    "I am a curious, creative person with a passion for technology, design and innovation. "
    "I love exploring new ideas, understanding how things work and turning what I imagine into real projects. "
    "My experience combines programming, 3D design and software development, with a particular interest in "
    "artificial intelligence and emerging technologies. Much of what I know comes from experimenting, "
    "researching and taking on new challenges independently. I enjoy finding original solutions, paying "
    "attention to detail and constantly learning, always with the ambition to create things that go a little "
    "beyond the conventional."
)
SKILLS = [
    ("3D DESIGN & MODELING", "Blender, materials and rendering."),
    ("PROGRAMMING", "Software and application development."),
    ("ARTIFICIAL INTELLIGENCE", "LLMs, local AI and model integration."),
    ("GAME DEVELOPMENT", "Unity and Unreal Engine."),
    ("INTERFACE DESIGN", "UI/UX and prototyping."),
    ("AUTOMATION", "APIs and workflows."),
    ("SYSTEMS & HARDWARE", "Technology configuration and integration."),
    ("PROBLEM SOLVING", "Research, creativity and self-directed learning."),
]


def wrap_copy(s, text, width):
    lines, current = [], ""
    for word in text.split():
        candidate = (current+" "+word).strip()
        measured = s.text(candidate, 0, 0, 36, "subtitle")
        s.parts.pop()
        if current and measured > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def about(mobile=False):
    w, pad = (600, 35) if mobile else (1200, 35)
    s = SVG(w, 1, "About me", ABOUT_TEXT)
    lines = wrap_copy(s, ABOUT_TEXT, w-2*pad)
    copy_y = 340 if mobile else 430
    skills_y = copy_y + len(lines)*46 + 35
    columns, gutter = (1, 0) if mobile else (2, 36)
    column_width = (w-2*pad-gutter)/columns
    skill_rows = []
    cursor = skills_y + 85
    for row in range(0,len(SKILLS),columns):
        items=[]
        for col,(name,desc) in enumerate(SKILLS[row:row+columns]):
            wrapped = wrap_copy(s, desc, column_width)
            items.append((pad+col*(column_width+gutter),name,wrapped))
        row_height = 56+22+max(len(item[2]) for item in items)*46+28
        skill_rows.append((cursor,items))
        cursor += row_height
    s.height = cursor+7
    s.parts = [f'<rect width="{w}" height="{s.height}" fill="#000"/>']
    abstract(s, mobile, ribbon=True, hue=200)
    s.fitted("ABOUT ME.", pad, 35, w-2*pad, 90 if mobile else 145)
    gap = 24 if mobile else 40
    size = (w-2*pad-gap*3)/4
    for index,file in enumerate(sorted((OUT/"website").glob("EYE_*.png"))):
        image = base64.b64encode(file.read_bytes()).decode()
        s.raw(f'<image href="data:image/png;base64,{image}" x="{pad+index*(size+gap)}" y="{(145 if mobile else 200)+(index%2)*12}" width="{size}" height="170"/>')
    for i,line in enumerate(lines):
        s.text(line,pad,copy_y+i*46,36,"subtitle")
    s.text("SKILLS",pad,skills_y+42,56,"heading")
    for row_index,(y,items) in enumerate(skill_rows):
        for col,(x,name,description) in enumerate(items):
            width = s.text(name,0,0,36,"heading")+32
            s.parts.pop()
            s.text(name,x+16,y+39,36,"heading")
            lettering = s.parts.pop().replace('fill="#ffffff"','fill="#000000"')
            mask=f"skill-{row_index}-{col}"
            s.raw(f'<defs><mask id="{mask}" maskUnits="userSpaceOnUse" x="{x}" y="{y}" width="{width}" height="56" style="mask-type:luminance"><rect x="{x}" y="{y}" width="{width}" height="56" fill="#fff"/>{lettering}</mask></defs>')
            s.raw(f'<rect x="{x}" y="{y}" width="{width}" height="56" fill="#fff" mask="url(#{mask})"/>')
            for i,line in enumerate(description):
                s.text(line,x,y+100+i*46,36,"subtitle")
    s.save("about-mobile.svg" if mobile else "about.svg")


def project(mobile=False):
    w, pad = (600, 35) if mobile else (1200, 35)
    h = 315 if mobile else 380
    s = SVG(w, h, "PORTFOLIO", "Interactive personal portfolio")
    abstract(s, mobile, ribbon=True, hue=100)
    inset = pad
    s.fitted("PORTFOLIO", inset, 75, w-2*inset, 85 if mobile else 145)
    icon_size, padding, gap = 26, 12, 10
    label_width = s.text("OPEN", 0, 0, 36, "subtitle")
    s.parts.pop()
    button_width = padding*2 + icon_size + gap + label_width
    button_height = icon_size + padding*2
    bx, by = w-pad-button_width, (184 if mobile else 250)
    lines = ["My space for design,", "development and ideas", "on the web."] if mobile else ["My space for design, development and ideas on the web."]
    for i, line in enumerate(lines):
        s.text(line, inset, (207 if mobile else 286)+i*42, 36, "subtitle")
    s.text("OPEN", bx+padding+icon_size+gap, by+padding+icon_size, 36, "subtitle")
    label = s.parts.pop().replace('fill="#ffffff"', 'fill="#000000"')
    ax, ay = bx+padding+2, by+padding+2
    arrow = f'<path d="M{ax} {ay+22}l22-22m-22 0h22v22" fill="none" stroke="#000" stroke-width="4"/>'
    s.raw(f'<defs><mask id="open-cutout" maskUnits="userSpaceOnUse" x="{bx}" y="{by}" width="{button_width}" height="{button_height}" style="mask-type:luminance"><rect x="{bx}" y="{by}" width="{button_width}" height="{button_height}" fill="#fff"/>{arrow}{label}</mask></defs>')
    s.raw(f'<rect x="{bx}" y="{by}" width="{button_width}" height="{button_height}" fill="#fff" mask="url(#open-cutout)"/>')
    s.save(f"portfolio{'-mobile' if mobile else ''}.svg")


def socials(mobile=False):
    # Equal-height image segments form one black strip, while each link stays clickable.
    # 5% leading space + four 15% buttons + 35% trailing space = 100%.
    # An inner 10px / 8px offset aligns the first icon with each panel's text.
    width, height, button = (72, 160, 48) if mobile else (144, 200, 64)
    suffix = "-mobile" if mobile else ""
    icons = json.loads((ROOT/"data/social-icons.json").read_text())
    for name, markup in icons.items():
        s = SVG(width, height, name)
        x, y = (width-6-button)/2, (height-button)/2
        source = OUT / "website/icons" / f"{name}.svg"
        if name == "linkedin":
            document = ET.fromstring(source.read_text())
            paths = []
            for node in document.iter():
                if node.tag.split("}")[-1] == "path":
                    node.set("fill", "#000000" if node.get("fill", "").upper() == "#FFFFFF" else "#ffffff")
                    paths.append(ET.tostring(node, encoding="unicode"))
            icon = '<g transform="translate(12.16 12.16) scale(1.653333)">'+''.join(paths)+'</g>'
        elif source.exists():
            raster = Image.open(io.BytesIO(svg2png(url=str(source), output_width=160, output_height=160))).convert("RGBA")
            ink = Image.new("RGBA", raster.size, (0, 0, 0, 0))
            ink.putalpha(raster.getchannel("A"))
            buffer = io.BytesIO()
            ink.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode()
            icon = f'<image href="data:image/png;base64,{encoded}" x="12.16" y="12.16" width="39.68" height="39.68"/>'
        else:
            icon = '<g transform="translate(32 32) scale(1.42) translate(-32 -32)">'+markup.replace("#ffffff", "#000000")+'</g>'
        s.raw(f'<rect x="1" y="1" width="{width-6}" height="{height-2}" fill="#ffffff"/>')
        s.raw(f'<g transform="translate({x} {y}) scale({button/64})">{icon}</g>')
        s.save(f"social-{name}{suffix}.svg")
    SVG(18 if mobile else 36, height, "").save(f"social-spacer-left{suffix}.svg")
    SVG(294 if mobile else 588, height, "").save(f"social-spacer-right{suffix}.svg")


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
    _, end, _, _ = activity_window(data)
    w, pad = (600, 35) if mobile else (1200, 35)
    cell = 44 if mobile else 48
    columns = int((w-2*pad)//cell)
    days = sorted((day for week in data["calendar"]["weeks"] for day in week["contributionDays"] if day["date"] <= end.isoformat()), key=lambda day: day["date"])[-columns*2:]
    grid_y = 200 if mobile else 255
    s = SVG(w, grid_y+2*cell+35, "Activity", "Public GitHub contributions")
    s.fitted("ACTIVITY.", pad, 30, w-2*pad, 90 if mobile else 145)
    s.text(f'{days[0]["date"]} — {days[-1]["date"]}', pad, grid_y-25, 36, "subtitle")
    levels = {"NONE":0,"FIRST_QUARTILE":1,"SECOND_QUARTILE":2,"THIRD_QUARTILE":3,"FOURTH_QUARTILE":4}
    peak = max((day["contributionCount"] for day in days), default=1) or 1
    for i, day in enumerate(days):
        count = day["contributionCount"]
        level = levels.get(day.get("contributionLevel"), 0 if not count else min(4,max(1,math.ceil(count/peak*4))))
        shade = round(255*[.18,.35,.55,.78,1][level])
        x,y = pad+(i%columns)*cell, grid_y+(i//columns)*cell
        s.raw(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="rgb({shade},{shade},{shade})" shape-rendering="crispEdges"><title>{day["date"]}: {count} contributions</title></rect>')
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
