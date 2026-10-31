"""Build the SiteGuard pitch deck (Team HF27-0030) with python-pptx."""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ASSETS = Path(sys.argv[1])
OUT = Path(sys.argv[2])

INK, ORANGE, YELLOW, PAPER, CARD, LINE = "12202B", "FF6A13", "FFC400", "F5F1E8", "FFFDF8", "E4DCCB"
GOOD, WARN, BAD, BLUE, GREY, SOFT = "1F8A5B", "D98A00", "D1332E", "2B6CB0", "6B7580", "FFF1D6"
HEAD, BODY = "Segoe UI Semibold", "Segoe UI"
TEAM = "Team HF27-0030"
W, H = 13.333, 7.5

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]


def rgb(hex_):
    return RGBColor.from_string(hex_)


def rect(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, line_w=1.0, radius=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(line_w)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def text(slide, x, y, w, h, content, size=18, color=INK, bold=False, font=BODY, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.0, space_after=0):
    """content: a string, or a list of strings / (string, {overrides}) paragraphs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    paragraphs = content if isinstance(content, list) else [content]
    for i, item in enumerate(paragraphs):
        opts = {}
        if isinstance(item, tuple):
            item, opts = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = opts.get("align", align)
        p.line_spacing = spacing
        p.space_after = Pt(opts.get("space_after", space_after))
        r = p.add_run()
        r.text = item
        r.font.name = opts.get("font", font)
        r.font.size = Pt(opts.get("size", size))
        r.font.bold = opts.get("bold", bold)
        r.font.color.rgb = rgb(opts.get("color", color))
    return box


def stripe(slide, y, h=0.22, dark=INK, light=YELLOW, step=0.42):
    """A hazard-stripe band made of slanted blocks."""
    x, flip = -0.3, False
    while x < W + 0.3:
        s = slide.shapes.add_shape(MSO_SHAPE.PARALLELOGRAM, Inches(x), Inches(y), Inches(step * 1.3), Inches(h))
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(light if flip else dark)
        s.line.fill.background()
        s.shadow.inherit = False
        x += step
        flip = not flip


def background(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(color)


def notes(slide, body):
    slide.notes_slide.notes_text_frame.text = body


counter = {"n": 0}


def base(title, kicker=""):
    """A standard content slide: paper background, orange marker, title, footer."""
    s = prs.slides.add_slide(BLANK)
    counter["n"] += 1
    background(s, PAPER)
    rect(s, 0, 0, W, 0.14, fill=INK)
    rect(s, 0.6, 0.62, 0.12, 0.78, fill=ORANGE)
    if kicker:
        text(s, 0.85, 0.42, 9, 0.35, kicker.upper(), size=12, color=ORANGE, bold=True, font=HEAD)
    text(s, 0.85, 0.72, 11.8, 0.8, title, size=32, color=INK, font=HEAD, anchor=MSO_ANCHOR.TOP)
    rect(s, 0, H - 0.5, W, 0.5, fill=INK)
    text(s, 0.6, H - 0.46, 8, 0.4, f"{TEAM}   |   SiteGuard: PPE Compliance Detection", size=11, color="C8D0D6", anchor=MSO_ANCHOR.MIDDLE)
    text(s, W - 1.6, H - 0.46, 1.0, 0.4, str(counter["n"] + 1), size=11, color=YELLOW, bold=True, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    return s


def card(slide, x, y, w, h, head, body, accent=ORANGE, head_size=18, body_size=14, fill=CARD):
    rect(slide, x, y, w, h, fill=fill, line=LINE)
    rect(slide, x, y, 0.09, h, fill=accent)
    text(slide, x + 0.25, y + 0.14, w - 0.4, 0.5, head, size=head_size, bold=True, font=HEAD, color=INK)
    text(slide, x + 0.25, y + 0.68, w - 0.4, h - 0.8, body, size=body_size, color="3B4A56", spacing=1.05)


def picture(slide, name, x, y, w=None, h=None):
    kwargs = {}
    if w:
        kwargs["width"] = Inches(w)
    if h:
        kwargs["height"] = Inches(h)
    pic = slide.shapes.add_picture(str(ASSETS / name), Inches(x), Inches(y), **kwargs)
    pic.line.color.rgb = rgb(LINE)
    pic.line.width = Pt(1.5)
    return pic


# ---------------------------------------------------------------- 1. title
s = prs.slides.add_slide(BLANK)
background(s, INK)
stripe(s, 0, 0.3)
stripe(s, H - 0.3, 0.3)
text(s, 0.9, 1.35, 9, 0.4, "KLS VISHWANATHRAO DESHPANDE INSTITUTE OF TECHNOLOGY, HALIYAL", size=13, color=YELLOW, bold=True, font=HEAD)
text(s, 0.9, 1.7, 9, 0.35, "Department of CSE & CSE (AI & ML)   |   Theme: Computer Vision", size=13, color="C8D0D6")
text(s, 0.9, 2.45, 11.5, 1.2, "SITEGUARD", size=72, color="FFFFFF", bold=True, font=HEAD)
text(s, 0.9, 3.6, 11.5, 0.8, "PPE Compliance Detection", size=36, color=ORANGE, font=HEAD)
text(s, 0.9, 4.5, 11, 0.9, "We don't ask if a helmet is in the picture.\nWe ask whose head it is on.", size=22, color="E7EBEE", spacing=1.1)
rect(s, 0.9, 5.75, 4.6, 0.62, fill=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 0.9, 5.75, 4.6, 0.62, "TEAM ID: HF27-0030", size=22, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 5.8, 5.75, 6.5, 0.62, "Problem Statement 1  |  Computer Vision", size=18, color="C8D0D6", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.9, 6.55, 11, 0.35, "Team members: [Name 1]   [Name 2]   [Name 3]   [Name 4]", size=13, color="9AA6B0")
notes(s, "Introduce the team (ID HF27-0030) and the project in one sentence: SiteGuard checks every worker in a photo or video for the protective equipment they should be wearing, "
         "and says exactly who is missing what. The tagline is the core idea: we match each helmet and vest to the specific worker wearing it.")

# ---------------------------------------------------------------- 2. problem
s = base("The problem", "Problem Statement 1")
rect(s, 0.6, 1.75, 6.3, 2.35, fill=INK)
text(s, 0.85, 1.9, 5.8, 2.1, [("“Supervisors cannot consistently spot workers without helmets or safety vests across busy industrial areas.”", {"size": 22, "color": "FFFFFF", "font": HEAD})], spacing=1.1)
text(s, 0.6, 4.3, 6.3, 1.2, [("Objective", {"bold": True, "color": ORANGE, "size": 14}),
                              "Build a vision system that detects each worker, determines whether that specific worker is wearing the required equipment, and flags violations."],
     size=15, color="3B4A56", spacing=1.05)
text(s, 7.3, 1.7, 5.4, 0.4, "CORE REQUIREMENTS", size=13, bold=True, color=ORANGE, font=HEAD)
reqs = ["Detect people, helmets and safety vests", "Associate each item with the person wearing it", "Apply compliance rules per worker",
        "Flag each non-compliant worker and the missing item", "Show annotated images with a per-worker verdict", "Generate a violation summary",
        "Handle crowds, occlusion, distance, poor lighting"]
text(s, 7.3, 2.1, 5.5, 3.5, [(f"■  {r}", {"space_after": 7}) for r in reqs], size=15, color=INK, spacing=1.05)
rect(s, 0.6, 5.75, 12.1, 0.75, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 5.75, 11.6, 0.75, "Constraint: a helmet detected anywhere in the image must not be taken to mean every worker in it is compliant.", size=17, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Read the problem statement as given. The last line is the heart of the problem: a model that only asks 'is there a helmet in this picture?' would clear everybody. "
         "Our whole design is built around not doing that.")

# ---------------------------------------------------------------- 3. solution
s = base("Our solution, at a glance", "What SiteGuard does")
steps = [("1", "A photo or short video goes in", "Any site photo, from a phone or a camera."),
         ("2", "Every worker gets their own verdict", "Each worker is numbered, boxed and judged separately."),
         ("3", "A violation summary comes out", "Counts, what is missing most, a table, CSV, JSON and PDF notices.")]
for i, (n, head, body) in enumerate(steps):
    x = 0.6 + i * 4.1
    rect(s, x, 1.85, 3.8, 2.6, fill=CARD, line=LINE)
    rect(s, x, 1.85, 3.8, 0.12, fill=ORANGE)
    text(s, x + 0.2, 2.1, 0.9, 0.9, n, size=44, bold=True, color=ORANGE, font=HEAD)
    text(s, x + 0.2, 2.95, 3.4, 0.7, head, size=18, bold=True, font=HEAD)
    text(s, x + 0.2, 3.6, 3.4, 0.8, body, size=14, color="3B4A56")
    if i < 2:
        a = rect(s, x + 3.83, 2.95, 0.3, 0.4, fill=INK, shape=MSO_SHAPE.RIGHT_ARROW)
text(s, 0.6, 4.75, 4, 0.4, "WHAT THE COLOURS MEAN", size=12, bold=True, color=ORANGE, font=HEAD)
for i, (c, word, d) in enumerate([(GOOD, "GREEN: OK", "has everything required"), (BAD, "RED: VIOLATION", "missing an item, which one is named"), (WARN, "AMBER: NEEDS REVIEW", "cannot be judged fairly, a person checks")]):
    x = 0.6 + i * 4.1
    rect(s, x, 5.2, 0.55, 0.55, fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
    text(s, x + 0.7, 5.12, 3.2, 0.4, word, size=16, bold=True, font=HEAD, color=c)
    text(s, x + 0.7, 5.5, 3.2, 0.5, d, size=13, color="3B4A56")
notes(s, "Three things: a photo goes in, each worker gets a verdict, and a summary comes out. Green means everything required is there, red means something specific is missing, "
         "and amber means we are not sure, so a person should look rather than us accusing someone.")

# ---------------------------------------------------------------- 4. pipeline
s = base("How it works", "Six steps")
pipe = [("Brighten", "if the photo is dark", "enhance"), ("Detect", "person, helmet, vest", "AI model"), ("Match", "each item to its worker", "our logic"),
        ("Judge", "rules per worker", "our logic"), ("Annotate", "green, red, amber", "our code"), ("Summarise", "table, report, export", "our code")]
bw, gap = 1.8, 0.26
x0 = (W - (6 * bw + 5 * gap)) / 2
for i, (head, sub, tag) in enumerate(pipe):
    x = x0 + i * (bw + gap)
    ai = tag == "AI model"
    rect(s, x, 2.0, bw, 2.1, fill=INK if ai else CARD, line=None if ai else LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    text(s, x, 2.1, bw, 0.7, f"{i + 1}", size=30, bold=True, color=ORANGE, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x, 2.75, bw, 0.5, head, size=19, bold=True, font=HEAD, color="FFFFFF" if ai else INK, align=PP_ALIGN.CENTER)
    text(s, x + 0.08, 3.25, bw - 0.16, 0.7, sub, size=12.5, color="C8D0D6" if ai else "3B4A56", align=PP_ALIGN.CENTER)
    rect(s, x + 0.35, 4.28, bw - 0.7, 0.34, fill=ORANGE if ai else SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
    text(s, x + 0.35, 4.28, bw - 0.7, 0.34, tag.upper(), size=10, bold=True, color=INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < 5:
        rect(s, x + bw + 0.02, 2.9, 0.22, 0.32, fill=ORANGE, shape=MSO_SHAPE.RIGHT_ARROW)
rect(s, 0.6, 5.2, 12.1, 1.2, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 5.25, 11.6, 1.1, [("Only step 2 uses the AI model.", {"bold": True, "size": 18, "font": HEAD}),
                                 "Everything else is logic we designed and tested: 154 automatic tests check the matching and the rules with hand-made boxes."], size=15, color="3B4A56", anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Walk left to right. Only the detection step uses a trained AI model. The matching, the rules, the drawing and the summary are ordinary code we wrote and tested. "
         "That is why we can explain every decision the system makes.")

# ---------------------------------------------------------------- 5. matching
s = base("The key idea: match each item to the right worker", "Our core logic")
px, py, pw, ph = 0.9, 2.2, 2.4, 4.0
rect(s, px, py, pw, ph, fill=None, line=INK, line_w=2.5)
rect(s, px, py - 0.1 * ph + 0.0, pw, 0.45 * ph * 0.35 + 0.1 * ph - 0.0, fill="FFD9BF", line=ORANGE, line_w=1.5)
rect(s, px, py + 0.2 * ph, pw, 0.55 * ph, fill="FFF1B8", line=YELLOW, line_w=1.5)
hel = rect(s, px + 0.65, py + 0.08, 1.1, 0.6, fill=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
text(s, px + 0.65, py + 0.08, 1.1, 0.6, "helmet", size=12, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
vst = rect(s, px + 0.35, py + 1.4, 1.7, 1.6, fill=YELLOW, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
text(s, px + 0.35, py + 1.4, 1.7, 1.6, "vest", size=14, bold=True, color=INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, px + pw + 0.1, py - 0.05, 2.0, 0.4, "HEAD ZONE", size=12, bold=True, color=ORANGE, font=HEAD)
text(s, px + pw + 0.1, py + 0.28, 2.0, 0.5, "top 35% of the person box", size=11, color=GREY)
text(s, px + pw + 0.1, py + 1.1, 2.0, 0.4, "TORSO ZONE", size=12, bold=True, color=WARN, font=HEAD)
text(s, px + pw + 0.1, py + 1.43, 2.0, 0.5, "the middle of the body", size=11, color=GREY)
text(s, px, py + ph + 0.05, pw, 0.35, "one worker's box", size=11, color=GREY, align=PP_ALIGN.CENTER)
rect(s, 6.4, 1.7, 6.3, 1.6, fill=CARD, line=LINE)
text(s, 6.6, 1.78, 5.9, 1.5, [("A helmet counts only if it is on that worker's head", {"bold": True, "size": 17, "font": HEAD}),
                              "Its centre must sit in the head zone, and most of it must overlap the zone."], size=14, color="3B4A56", spacing=1.05)
rect(s, 6.4, 3.45, 6.3, 1.25, fill=CARD, line=LINE)
text(s, 6.6, 3.52, 5.9, 1.2, [("Each item belongs to at most one worker", {"bold": True, "size": 17, "font": HEAD}),
                              "One helmet can never clear two people, even when they stand close together."], size=14, color="3B4A56", spacing=1.05)
rect(s, 6.4, 4.85, 6.3, 1.45, fill=INK)
text(s, 6.6, 4.92, 5.9, 1.4, [("Helmet on a table or in a hand?", {"bold": True, "size": 17, "font": HEAD, "color": YELLOW}),
                              ("It is in nobody's head zone, so nobody gets credit. The worker is flagged.", {"color": "FFFFFF"})], size=14, spacing=1.05)
notes(s, "This is the idea that answers the problem's constraint. Every worker has a head zone and a torso zone. A helmet only counts when it sits in that worker's head zone, and every helmet or vest is given to at most one worker. "
         "So a helmet lying on a table, or hanging from someone's hand, is outside every head zone and clears nobody.")

# ---------------------------------------------------------------- 6. outcomes
s = base("Three outcomes, not two", "Never accuse what we cannot see")
cards = [(GOOD, "COMPLIANT", "Everything required is found on this worker.", "Worker 1: OK"),
         (BAD, "VIOLATION", "A required item is clearly missing, and the label names it.", "Worker 2: NO HELMET + NO VEST"),
         (WARN, "NEEDS REVIEW", "The worker is too small, cut off, crowded, or the evidence is weak.", "Worker 3: REVIEW")]
for i, (c, head, body, example) in enumerate(cards):
    x = 0.6 + i * 4.1
    rect(s, x, 1.85, 3.8, 3.5, fill=CARD, line=LINE)
    rect(s, x, 1.85, 3.8, 0.85, fill=c)
    text(s, x, 1.85, 3.8, 0.85, head, size=24, bold=True, color="FFFFFF", font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, 2.95, 3.3, 1.2, body, size=15, color="3B4A56", spacing=1.05)
    rect(s, x + 0.25, 4.35, 3.3, 0.6, fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.15)
    text(s, x + 0.25, 4.35, 3.3, 0.6, example, size=13, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.6, 5.65, 12.1, 0.85, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 5.65, 11.6, 0.85, "Weak evidence blocks an accusation: a helmet seen with low confidence sends the worker to review, never straight to a violation.", size=16, bold=True, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Most systems say compliant or not. We added a third answer. If a worker is tiny, cut off by the edge of the photo, hidden in a crowd, or we only have a faint guess about their helmet, we say 'needs review' "
         "so a person decides. This keeps false accusations low.")

# ---------------------------------------------------------------- 7. hard conditions
s = base("Handling the hard conditions", "From the problem statement")
items = [("Multiple workers", "Every person is numbered left to right and judged on their own. Labels are placed so they never overlap in a crowd.", ORANGE),
         ("Partial occlusion", "A worker who is cut off, hidden or crowded becomes NEEDS REVIEW instead of a false accusation.", WARN),
         ("Distance", "Zoomed-in tiles let small, far-away workers be seen. Very small workers are sent to review.", BLUE),
         ("Poor lighting", "Dark photos are detected and their contrast is boosted automatically before detection.", INK)]
for i, (head, body, c) in enumerate(items):
    x, y = 0.6 + (i % 2) * 6.15, 1.8 + (i // 2) * 2.35
    card(s, x, y, 5.95, 2.1, head, body, accent=c, head_size=20, body_size=15)
notes(s, "Each hard condition from the problem has a specific answer. Multiple workers: individual verdicts. Occlusion: the review state. Distance: zoomed tiles. Poor lighting: automatic contrast enhancement. "
         "We tested these on real site photos, and we are honest about what still fails.")

# ---------------------------------------------------------------- 8. hard-case proof
s = base("The hard cases, on real site photos", "Checked by eye")
picture(s, "hand.jpg", 0.6, 1.65, h=4.85)
picture(s, "table.jpg", 9.0, 1.65, h=4.85)
text(s, 4.55, 1.65, 4.3, 0.4, "HELMET IN HAND", size=13, bold=True, color=ORANGE, font=HEAD)
text(s, 4.55, 2.0, 4.3, 1.5, "Both foreground workers hold their yellow helmets at their sides. Both are flagged NO HELMET.", size=15, color="3B4A56", spacing=1.05)
text(s, 4.55, 3.55, 4.3, 0.4, "HELMET ON A TABLE", size=13, bold=True, color=ORANGE, font=HEAD)
text(s, 4.55, 3.9, 4.3, 1.6, "The helmet on the table is credited to nobody. The two bare-headed seated workers are flagged NO HELMET.", size=15, color="3B4A56", spacing=1.05)
rect(s, 4.55, 5.55, 4.3, 0.95, fill=SOFT, line=YELLOW, line_w=2)
text(s, 4.7, 5.55, 4.0, 0.95, "The constraint from the problem statement, shown on real photos.", size=13.5, bold=True, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Left: two workers holding their helmets in their hands. The system flags both as NO HELMET, because a helmet in the hand is not on the head. "
         "Right: a helmet sitting on a table. It is not credited to anyone, and the bare-headed workers are flagged. One note for honesty: in the right photo, one seated worker was sent to review rather than flagged as a violation, because their seated pose confuses the body zones.")

# ---------------------------------------------------------------- 9. results
s = base("How well does it work?", "Measured on photos the model never saw")
stats = [("0.876", "mean detection score (mAP50) on 314 held-out photos", INK), ("0.918", "of people flagged for no helmet really had none (precision)", GOOD),
         ("0.812", "of no-helmet workers are flagged automatically (0.958 with 'send to review')", GOOD), ("12.9%", "of labelled workers were not found at all", BAD)]
for i, (num, label, c) in enumerate(stats):
    x, y = 0.6 + (i % 2) * 3.0, 1.75 + (i // 2) * 1.85
    rect(s, x, y, 2.8, 1.65, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 1.65, fill=c)
    text(s, x + 0.25, y + 0.05, 2.4, 0.85, num, size=44, bold=True, color=c, font=HEAD)
    text(s, x + 0.25, y + 0.9, 2.45, 0.75, label, size=12.5, color="3B4A56", spacing=1.0)
picture(s, "clean.jpg", 6.8, 1.75, w=5.9)
text(s, 6.8, 5.05, 5.9, 0.4, "A fully equipped worker and a distant one: both OK", size=12, color=GREY, align=PP_ALIGN.CENTER)
rect(s, 0.6, 5.5, 12.1, 1.0, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 5.5, 11.6, 1.0, "Measured with scripts anyone can re-run, on 661 labelled workers (60 px or taller). We do not claim 99.99%: no detection system honestly can. "
                              "Known gaps: small or hidden workers, hi-vis shirts taken for vests, backlit workers. Our earlier by-eye review of 11 photos: 34 of 45 right, 9 sent to review, 2 wrong.", size=13, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
notes(s, "Every number here comes from a script in the project that can be re-run: scripts/compare_models.py for the detection score and scripts/eval_workers.py for the per-worker verdicts. "
         "Of the 661 labelled workers, 78 no-helmet workers were caught correctly, 7 workers wearing a helmet were wrongly flagged, 4 were missed and 14 more were sent to review. In dark photos the night model cut false alarms from 36 to 8 (precision 0.890). "
         "A second model double-checks every helmet call before it is sent on: it held back none of 88 real violations and caught 2 of 6 false alarms (a small sample). "
         "Do not say 99.99%. If asked, say the figures above are what was measured, and list the known gaps.")

# ---------------------------------------------------------------- 10. model and data
s = base("The AI model and the data", "Fine-tuned, not trained from scratch")
cols = [("Model", ["YOLO11s (Ultralytics), pretrained", "Four classes: person, helmet, vest, head (bare or covered)", "Checked by a second model and an object check"], ORANGE),
        ("Data (both public, credited)", ["Construction-PPE: 1,416 photos", "CHVG: 1,699 photos, CC BY 4.0", "Missing items are inferred, not trained as a class"], BLUE),
        ("Training", ["Round 1: 60 epochs, 36 minutes", "Round 2: 30 epochs, merged data; round 3 adds a head class", "A larger model (YOLO11m) scored lower, 0.819, so it was not used"], INK)]
for i, (head, lines, c) in enumerate(cols):
    x = 0.6 + i * 4.1
    rect(s, x, 1.75, 3.8, 2.75, fill=CARD, line=LINE)
    rect(s, x, 1.75, 3.8, 0.1, fill=c)
    text(s, x + 0.2, 1.95, 3.4, 0.45, head, size=17, bold=True, font=HEAD)
    text(s, x + 0.2, 2.5, 3.45, 2.0, [(f"■  {l}", {"space_after": 5}) for l in lines], size=13, color="3B4A56", spacing=1.02)
text(s, 0.6, 4.7, 8, 0.4, "DETECTION SCORE ON 314 HELD-OUT PHOTOS (AP at IoU 0.5)", size=12, bold=True, color=ORANGE, font=HEAD)
hdr = ["Class", "Score"]
rows = [("Person", "0.925"), ("Helmet", "0.941"), ("Vest", "0.901"), ("Head (bare head)", "0.736")]
for r, row in enumerate([tuple(hdr)] + rows):
    for c, cell in enumerate(row):
        x = 0.6 + [0, 3.2][c]
        wc = [3.1, 1.4][c]
        y = 5.05 + r * 0.38
        rect(s, x, y, wc, 0.36, fill=INK if r == 0 else CARD, line=LINE)
        text(s, x + 0.08, y, wc - 0.1, 0.36, cell, size=12, bold=(r == 0), color="FFFFFF" if r == 0 else INK, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
text(s, 5.6, 5.05, 7.1, 1.5, "Mean 0.876. The head class is the hardest. Tuning the confidence thresholds, test-time augmentation and a tracker that uses appearance were each tried and did not help, "
                              "so the defaults were kept. Details: docs/ACCURACY_MEASURED.md.", size=12, color=GREY, spacing=1.0)
notes(s, "We did not train from scratch. We fine-tuned a pretrained YOLO model on two public datasets, both credited. The scores are measured on photos the model never trained on. "
         "We also tried a bigger model, different thresholds, test-time augmentation and a different tracker; none beat the current setup, which is why they are not used.")

# ---------------------------------------------------------------- 11. built
s = base("Built beyond detection", "Tools around the model")
built = [("Three sites", "A supervisor panel, an employee portal and a demo desk, each on its own address, with normal sign-in (code and password)."),
         ("Instant, spoken alerts", "Only people who broke a rule are called out by name, at most once every 10 minutes. The employee sees it in their own feed at once."),
         ("One violation a day", "Caught again the same day: the count goes up. Next day: a new violation. 3 in 30 days propose a penalty a supervisor must approve."),
         ("Names and sightings", "Face matching with consent; a made-up name for anyone whose face is unclear. A log of who was seen, when and where."),
         ("Cross-checks and remarks", "An object check, a second-model check on helmet calls, and an auto-written remark on every case that a supervisor can edit."),
         ("Quality", "201 Python tests and 21 web tests, plus a smoke test that walks one case through the whole system.")]
for i, (head, body) in enumerate(built):
    x, y = 0.6 + (i % 3) * 4.1, 1.8 + (i // 3) * 2.45
    card(s, x, y, 3.8, 2.2, head, body, accent=[ORANGE, BLUE, GOOD][i % 3], head_size=17, body_size=12.5)
text(s, 0.6, 6.6, 12, 0.3, "Accounts, names and salaries are made up (password is the code plus @123). Live camera and spoken alerts are not yet tested on real site footage.", size=11.5, color=GREY)
notes(s, "These are the supporting pieces built around the model. Be upfront: accounts, names, salaries and penalty amounts are made up for the demo, and the live camera and the spoken alerts have not been tested on real site footage.")

# ---------------------------------------------------------------- 12. roadmap
s = base("The product, and what comes next", "What is built, partly built and planned")
road = [("Three sites with sign-in", "Supervisor panel (every employee, cases, remarks, penalties), employee portal (personal feed, salary, disputes) and the demo desk.", "BUILT", GOOD),
        ("One violation a day, penalties", "At most one violation per person per day; 3 in 30 days propose a penalty, issued only when a supervisor approves. Management sets the real values.", "BUILT", GOOD),
        ("Alerts, cross-checks, remarks", "Spoken alerts for violators only, object and second-model checks, and an auto-written remark per case.", "BUILT", GOOD),
        ("Naming people", "Face matching works when the face is 48 px or wider. Clothes are a weak signal. Unclear faces get a made-up name tied to that footage.", "PARTLY", WARN),
        ("Fall and collapse alerts", "Alert from body shape plus an optional learned detector: 53% of falls caught (24% in low light), 7% false alarms on normal clips. It cannot say why someone is down.", "PARTLY", WARN),
        ("Before real use", "Real accounts and passwords, consent and data retention, hi-vis and life-jacket training photos, and hosting (sites on Vercel; the API and detector on a server).", "PLANNED", BLUE)]
for i, (head, body, status, c) in enumerate(road):
    x, y = 0.6 + (i % 2) * 6.15, 1.7 + (i // 2) * 1.6
    rect(s, x, y, 5.95, 1.45, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 1.45, fill=c)
    text(s, x + 0.25, y + 0.07, 3.8, 0.4, head, size=16, bold=True, font=HEAD)
    rect(s, x + 4.55, y + 0.12, 1.25, 0.3, fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
    text(s, x + 4.55, y + 0.12, 1.25, 0.3, status, size=10, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, y + 0.5, 5.55, 0.95, body, size=12, color="3B4A56", spacing=1.0)
notes(s, "Built means working and tested in our own checks; partly means it works with stated limits; planned means not started. Two design choices to highlight: "
         "a catch becomes a violation only when a supervisor confirms it, and any penalty is only proposed by the system and approved by a person.")

# ---------------------------------------------------------------- 13. stack and limits
s = base("Tech stack, limits and next steps", "Honest and specific")
rect(s, 0.6, 1.7, 5.7, 4.75, fill=CARD, line=LINE)
text(s, 0.85, 1.8, 5.2, 0.4, "TECH STACK", size=13, bold=True, color=ORANGE, font=HEAD)
stack = [("Python 3.12", "detector, face and object checks, service"), ("Ultralytics YOLO11, PyTorch", "detection model, GPU training"), ("OpenCV", "images, video, faces (YuNet and SFace)"),
         ("Node.js, Express, React", "API and the three sites"), ("NeDB (MongoDB-style)", "embedded database, swappable for MongoDB"), ("pytest, node:test", "201 + 21 tests, plus a smoke test")]
for i, (a, b) in enumerate(stack):
    y = 2.25 + i * 0.68
    text(s, 0.85, y, 5.2, 0.35, a, size=15, bold=True, font=HEAD)
    text(s, 0.85, y + 0.3, 5.2, 0.3, b, size=12, color=GREY)
rect(s, 6.6, 1.7, 6.1, 4.75, fill=CARD, line=LINE)
text(s, 6.85, 1.8, 5.6, 0.4, "WHERE IT STILL FAILS", size=13, bold=True, color=BAD, font=HEAD)
text(s, 6.85, 2.2, 5.6, 2.3, [(f"■  {l}", {"space_after": 4}) for l in ["12.9% of labelled workers are not found (small, hidden)", "Hi-vis shirts or life jackets can pass as a vest",
                                                                                 "Backlit workers can be wrongly flagged", "Faces under about 48 px cannot be recognised"]], size=13, color="3B4A56")
text(s, 6.85, 4.2, 5.6, 0.4, "NEXT STEPS", size=13, bold=True, color=GOOD, font=HEAD)
text(s, 6.85, 4.6, 5.6, 1.8, [(f"■  {l}", {"space_after": 4}) for l in ["Hard-negative photos (hi-vis shirts, life jackets)", "Test the live camera and spoken alerts on real footage",
                                                                              "Real accounts, consent and data retention before real use", "More photos of small and distant workers"]], size=13, color="3B4A56")
notes(s, "Start with the stack so the judges know it is ordinary, reproducible code. Then say plainly where it fails. Naming our own weaknesses and the plan to fix them earns more trust than claiming it is perfect. "
         "Credits: Ultralytics YOLO and the Construction-PPE dataset (AGPL-3.0), the CHVG dataset (CC BY 4.0), OpenCV's YuNet and SFace, and Claude as a coding assistant.")

# ---------------------------------------------------------------- 14. thanks
s = prs.slides.add_slide(BLANK)
counter["n"] += 1
background(s, INK)
stripe(s, 0, 0.3)
stripe(s, H - 0.3, 0.3)
text(s, 0.9, 1.6, 11.5, 1.2, "THANK YOU", size=64, color="FFFFFF", bold=True, font=HEAD)
text(s, 0.9, 2.9, 11.5, 1.2, "Every worker. Every item. One at a time.", size=30, color=ORANGE, font=HEAD)
text(s, 0.9, 4.0, 11.5, 1.3, ["SiteGuard checks each worker for the equipment they should wear,", "says exactly what is missing, and asks a person when it is not sure."], size=18, color="C8D0D6", spacing=1.15)
rect(s, 0.9, 5.55, 3.9, 0.62, fill=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 0.9, 5.55, 3.9, 0.62, "TEAM HF27-0030", size=22, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 5.1, 5.55, 7, 0.62, "Questions are welcome.", size=20, color="FFFFFF", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.9, 6.45, 11, 0.35, "KLS Vishwanathrao Deshpande Institute of Technology, Haliyal   |   CSE & CSE (AI & ML)", size=12, color="9AA6B0")
notes(s, "Close with the one-sentence summary and invite questions. If asked what is built versus planned, point to slide 11 (built) and slide 12 (roadmap).")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))




