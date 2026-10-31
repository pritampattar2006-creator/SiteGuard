"""The final 8-slide SiteGuard pitch (Team HF27-0030), written as a sales-and-proof story.

  python docs/deck/build_deck_final.py docs/deck docs/SiteGuard_Pitch_HF27-0030_final.pptx

Look and helpers come from build_deck_v2.py (everything before its first slide). Every number below is from docs/ACCURACY_MEASURED.md, config/ or a script that was run.
"""
import os
import sys
from pathlib import Path

# "classic" is the original orange and yellow look (the default). "teal" is the navy and teal look: set DECK_THEME=teal to build it.
THEME = os.environ.get("DECK_THEME", "classic")

_src = (Path(__file__).parent / "build_deck_v2.py").read_text(encoding="utf-8")
_prelude = _src[: _src.index("# ---------------------------------------------------------------- 1. title")]
if THEME == "teal":  # deep navy, teal and gold on a cool white page
    for _old, _new in [('INK, ORANGE, YELLOW, PAPER, CARD, LINE = "12202B", "FF6A13", "FFC400", "F5F1E8", "FFFDF8", "E4DCCB"',
                        'INK, ORANGE, YELLOW, PAPER, CARD, LINE = "0B1F3A", "0B9A92", "F5B83D", "F2F6FA", "FFFFFF", "D3DEE8"'),
                       ('GOOD, WARN, BAD, BLUE, GREY, SOFT = "1F8A5B", "D98A00", "D1332E", "2B6CB0", "6B7580", "FFF1D6"',
                        'GOOD, WARN, BAD, BLUE, GREY, SOFT = "2E9E5B", "E39B1B", "E0524A", "4F6BED", "5F6F7F", "E7F6F4"')]:
        assert _prelude.count(_old) == 1, _old
        _prelude = _prelude.replace(_old, _new)
exec(compile(_prelude, "build_deck_v2_prelude", "exec"))

if THEME == "teal":
    def stripe(slide, y, h=0.22, **_):
        """The title band of the teal theme: a teal bar over a thin gold line (the classic theme keeps the hazard stripe)."""
        rect(slide, 0, y, W, h * 0.62, fill=ORANGE)
        rect(slide, 0, y + h * 0.62, W, h * 0.38, fill=YELLOW)

ID_CHIP = YELLOW if THEME == "teal" else ORANGE  # the "TEAM HF27-0030" chip

MEMBERS = ["Pritam Pattar", "Raj Narewadi", "Prajwal Bellaki", "Manasadevi B", "Harusha M"]


def member_chips(slide, x, y, w=2.2, gap=0.12, h=0.5, fill=None, color="FFFFFF"):
    """One rounded chip per team member."""
    fill = fill or ("14325A" if THEME == "teal" else "24384A")
    for i, name in enumerate(MEMBERS):
        cx = x + i * (w + gap)
        rect(slide, cx, y, w, h, fill=fill, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3, line_w=1.25)
        text(slide, cx, y, w, h, name, size=13, bold=True, color=color, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


TEAM_LINE = "Team members: [Name 1]   [Name 2]   [Name 3]   [Name 4]"

# ================================================================ 1. title
s = prs.slides.add_slide(BLANK)
background(s, INK)
stripe(s, 0, 0.3)
stripe(s, H - 0.3, 0.3)
text(s, 0.9, 0.62, 11.5, 0.4, "KLS VISHWANATHRAO DESHPANDE INSTITUTE OF TECHNOLOGY, HALIYAL", size=13, color=YELLOW, bold=True, font=HEAD)
text(s, 0.9, 0.97, 11.5, 0.35, "Department of CSE & CSE (AI & ML)   |   Theme: Computer Vision   |   Problem Statement 1", size=13, color="C8D0D6")
text(s, 0.9, 1.5, 11.5, 1.2, "SITEGUARD", size=72, color="FFFFFF", bold=True, font=HEAD)
text(s, 0.9, 2.65, 11.5, 0.8, "PPE Compliance Detection for Construction Sites", size=30, color=ORANGE, font=HEAD)
rect(s, 0.9, 3.6, 0.08, 1.05, fill=ORANGE)
text(s, 1.15, 3.55, 11, 1.2, "“We don't ask if a helmet is in the picture.\nWe ask whose head it is on.”", size=24, color="E7EBEE", spacing=1.12)
rect(s, 0.9, 5.2, 4.6, 0.62, fill=ID_CHIP, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 0.9, 5.2, 4.6, 0.62, "TEAM  HF27-0030", size=22, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 5.8, 5.2, 6.8, 0.62, "SiteGuard: every worker, every item, one at a time", size=17, color="C8D0D6", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.9, 6.28, 6, 0.3, "TEAM MEMBERS", size=11, bold=True, color=YELLOW, font=HEAD)
member_chips(s, 0.9, 6.58, w=2.2, h=0.46)
notes(s, "Introduce the team (ID HF27-0030), the product (SiteGuard) and the idea in one breath: the quote. Most systems ask whether a helmet is somewhere in the picture; ours matches every helmet and vest to the worker wearing it. "
         "Fill in the team member names on this slide before presenting.")

# ================================================================ 2. problem statement
s = base("Our problem statement", "Problem Statement 1: PPE compliance detection")
rect(s, 0.6, 1.7, 5.3, 2.3, fill=INK)
text(s, 0.85, 1.82, 4.85, 2.1, [("“Supervisors cannot consistently spot workers without helmets or safety vests across busy industrial areas.”", {"size": 19, "color": "FFFFFF", "font": HEAD})], spacing=1.1)
text(s, 0.6, 4.15, 5.3, 1.5, [("What it really asks", {"bold": True, "color": ORANGE, "size": 13}),
                              "A system that looks at each worker separately, decides if that worker wears the required gear, and tells a supervisor exactly who is missing what, even in crowds, at a distance and in poor light."],
     size=13, color="3B4A56", spacing=1.05)
text(s, 6.2, 1.65, 6.5, 0.35, "THE REQUIREMENTS, AND HOW SITEGUARD MEETS EACH", size=12, bold=True, color=ORANGE, font=HEAD)
reqs = [("Detect each worker", "YOLO11 person detector plus zoomed tiles for distant workers"),
        ("Gear matched to that worker", "Head and torso zones, one item to one worker"),
        ("Flag the violation and the missing item", "Red verdict names it: NO HELMET, NO VEST"),
        ("Annotated image, verdict per worker", "Green, red or amber box on every worker"),
        ("Violation summary", "Counts, table, CSV, and a PDF notice for each case"),
        ("Crowds, occlusion, distance, poor light", "Tiles, night model, and 'needs review' when unsure")]
for i, (a, b) in enumerate(reqs):
    y = 2.05 + i * 0.66
    rect(s, 6.2, y, 6.5, 0.58, fill=CARD, line=LINE)
    rect(s, 6.2, y, 0.08, 0.58, fill=GOOD)
    text(s, 6.4, y + 0.02, 5.4, 0.3, a, size=12, bold=True, font=HEAD)
    text(s, 6.4, y + 0.29, 5.9, 0.28, b, size=10.5, color=GREY)
    text(s, 12.15, y + 0.08, 0.5, 0.42, "✔", size=16, bold=True, color=GOOD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.6, 6.05, 12.1, 0.75, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 6.05, 11.6, 0.75, "The catch in the brief: a helmet anywhere in the image must not mean every worker is compliant. This is exactly what SiteGuard is built around.", size=14.5, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Read the problem statement as given, then the right-hand column: every requirement in the brief has a matching feature. The last line is the heart of the problem: a model that only asks 'is there a helmet in the picture?' "
         "would clear every worker. Our whole design is built so that cannot happen.")

# ================================================================ 3. what we built and added
s = base("What we built, and what we added", "Everything below is working today")
rect(s, 0.6, 1.7, 5.9, 4.45, fill=CARD, line=LINE)
rect(s, 0.6, 1.7, 5.9, 0.1, fill=ORANGE)
text(s, 0.85, 1.9, 5.4, 0.4, "BUILT TO THE BRIEF", size=14, bold=True, color=ORANGE, font=HEAD)
core = ["Finds every person, helmet, vest and bare head", "Matches each item to the one worker wearing it", "A helmet in a hand or on a table never clears anyone",
        "Verdict per worker with a plain reason: green, red, amber", "Annotated photos and video, with evidence frames", "Handles dark scenes, small workers, crowds, objects",
        "Violation summary, CSV and PDF notices"]
text(s, 0.85, 2.35, 5.5, 2.4, [(f"■  {l}", {"space_after": 3}) for l in core], size=11.5, color="3B4A56", spacing=1.0)
for i, (label, sub, c) in enumerate([("GREEN: OK", "has everything required", GOOD), ("RED: VIOLATION", "names the missing item", BAD), ("AMBER: REVIEW", "a person checks", WARN)]):
    x = 0.85 + i * 1.88
    rect(s, x, 4.75, 1.75, 1.2, fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
    text(s, x, 4.85, 1.75, 0.4, label, size=12, bold=True, color="FFFFFF", font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x + 0.08, 5.3, 1.6, 0.6, sub, size=10.5, color="FFFFFF", align=PP_ALIGN.CENTER, spacing=1.0)
rect(s, 6.8, 1.7, 5.9, 4.45, fill=CARD, line=LINE)
rect(s, 6.8, 1.7, 5.9, 0.1, fill=BLUE)
text(s, 7.05, 1.9, 5.4, 0.4, "ADDED BEYOND THE BRIEF", size=14, bold=True, color=BLUE, font=HEAD)
added = ["Supervisor panel, employee portal and demo desk", "Penalties: proposed by rule or put by a supervisor", "PDF violation notice: the exact fault and its pictures",
         "Live phone or CCTV camera, auto-upright, voice alerts", "Face naming with consent; sector-specific gear rules", "Falling-object and welding watches; Streamlit 3-role app"]
text(s, 7.05, 2.35, 5.5, 2.1, [(f"■  {l}", {"space_after": 3}) for l in added], size=11.5, color="3B4A56", spacing=1.0)
rect(s, 7.05, 4.55, 5.4, 1.45, fill="FFF6DD", line=YELLOW, line_w=1.5)
text(s, 7.2, 4.58, 5.1, 0.35, "WORKER-DOWN ALERT: FALLS AND COLLAPSES", size=11, bold=True, color=BAD, font=HEAD)
text(s, 7.2, 4.92, 5.15, 1.05, "When a worker falls or collapses and stays still, for example from a fall or a medical emergency such as a suspected heart attack, a siren sounds and an accident report goes to the supervisor so help is sent at once.",
     size=11, color=INK, spacing=1.02)
rect(s, 0.6, 6.3, 12.1, 0.55, fill=INK)
text(s, 0.85, 6.3, 11.6, 0.55, "So far:  3 web portals + API   |   Streamlit app   |   worker-down, falling-object and welding watches   |   279 + 37 tests   |   smoke test passing", size=12.5, bold=True, color="FFFFFF", anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Left: the brief, fully built. Right: what we added because a detector alone does not run a safety programme: the three portals, penalties with a person in charge, a live camera, naming with consent, and extra watches. "
         "ABOUT THE FALL ALERT, be exact: it raises 'worker down' when someone falls or collapses and stays still, which covers a collapse from a heart attack or a trip. It detects the collapse, not the cause: it cannot tell a heart attack from a fall, "
         "and it does not diagnose anything. An alert means someone should check now. The learned fall detector is experimental (53% of acted falls caught per clip, 7% false alarms). "
         "The falling-object and welding watches use motion and brightness rules and were checked on test clips.")

# ================================================================ 4. architecture and tuning
s = base("System architecture and tuning", "How it is wired, and the values we measured")
boxes = [("INPUT", "Photo, video, live phone or CCTV camera", 2.05, INK), ("DETECTOR SERVICE  (Python)", "Brighten  >  YOLO11 detect  >  match to worker  >  rules  >  object check + second-model cross-check", 3.95, ORANGE),
         ("API  (Node)", "Cases, one violation a day, remarks, penalties, alerts, PDF notice", 2.3, BLUE), ("PORTALS", "Supervisor panel, employee portal, demo desk", 2.4, GOOD)]
x = 0.6
for i, (head, body, w, c) in enumerate(boxes):
    rect(s, x, 1.65, w, 1.35, fill=CARD, line=c, line_w=2)
    text(s, x + 0.1, 1.68, w - 0.2, 0.32, head, size=10.5, bold=True, color=c, font=HEAD)
    text(s, x + 0.1, 2.02, w - 0.2, 0.95, body, size=10.5, color="3B4A56", spacing=1.0)
    if i < 3:
        text(s, x + w - 0.02, 1.9, 0.4, 0.6, "→", size=24, bold=True, color=ORANGE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    x += w + 0.36
text(s, 0.6, 3.1, 12, 0.3, "TUNING: THE VALUES WE CHOSE, AND THE MEASURED REASON", size=11.5, bold=True, color=ORANGE, font=HEAD)
tune = [("Confidence 0.35 for person, helmet, vest", "Helmet raised from 0.30: removed 6 false helmets (caps, beanies) and lost 2 real ones, which go to review."),
        ("Head zone = top 35% of the worker's box", "A helmet counts only if 50% or more of it is in that zone; a vest only if 60% or more is on the person."),
        ("Dark picture = mean brightness below 70", "Brighten and use the night model: 'no helmet' precision 0.647 to 0.890; false alarms 36 to 8."),
        ("Zoomed tiles 2x2, 25% overlap, 960 px input", "Finds small and distant workers that one pass over the whole photo misses."),
        ("Model size: YOLO11s", "Scored 0.876 mean against 0.819 for the larger YOLO11m, so the smaller, faster model was chosen."),
        ("Backlit workers become 'needs review'", "Moves 9 of 93 no-helmet workers to review; a looser first version moved 25 and was rejected."),
        ("Worker-down alert threshold 0.95", "Per clip: 53% of falls caught with 7% false alarms. At 0.90: 62% and 19%. At 0.80: 81% and 31%."),
        ("Second-model cross-check on helmet calls", "Held back 0 of 88 real violations and caught 2 of 6 false alarms.")]
for i, (head, body) in enumerate(tune):
    x, y = 0.6 + (i % 2) * 6.15, 3.42 + (i // 2) * 0.86
    rect(s, x, y, 5.95, 0.78, fill=CARD, line=LINE)
    rect(s, x, y, 0.07, 0.78, fill=[ORANGE, BLUE, GOOD, WARN][(i // 2)])
    text(s, x + 0.18, y + 0.02, 5.7, 0.3, head, size=11, bold=True, font=HEAD)
    text(s, x + 0.18, y + 0.3, 5.7, 0.48, body, size=10, color="3B4A56", spacing=0.98)
notes(s, "Top: the architecture. A picture goes to the Python detector, which brightens it if dark, detects, matches each item to a worker, applies the rules and double-checks. Each catch goes to the Node API and then to the supervisor and employee portals. "
         "Bottom: every setting has a measured reason, which is the point of this slide. All values come from config/ and docs/ACCURACY_MEASURED.md and were measured on held-out photos. "
         "For the worker-down row, be exact: 0.95 was chosen to keep false alarms at 7%, so it is a deliberately cautious setting, and it is experimental.")

# ================================================================ 5. what we used and how we built it
s = base("What we used, and how we built it", "Data, models and the build flow")
cols = [("DATASETS (all public, credited)", ORANGE, ["Construction-PPE: 1,416 photos (AGPL-3.0)", "CHVG: 1,699 photos (CC BY 4.0)", "3,115 training photos in total", "Held-out test: 314 photos, 661 labelled workers", "GMDCSA24: 160 acted-fall clips (MIT) for the fall alert", "Darkened copies of training photos for the night model"]),
        ("MODELS AND STACK", BLUE, ["YOLO11s fine-tuned: person, helmet, vest, bare head", "A night-trained copy, used only in the dark", "Pose model for the object check and fall alert", "Second model for gloves, boots, goggles and cross-checks", "OpenCV YuNet and SFace for consented face naming", "Python, PyTorch, OpenCV; Node, Express, React; Streamlit"]),
        ("WHY THIS DESIGN", GOOD, ["Pretrained model, so far less data needed", "Matching and rules are our own logic, tested with hand-made boxes", "Every threshold lives in one config file", "Credits and licences kept in the README and docs"])]
for i, (head, c, lines) in enumerate(cols):
    x = 0.6 + i * 4.1
    rect(s, x, 1.7, 3.8, 3.1, fill=CARD, line=LINE)
    rect(s, x, 1.7, 3.8, 0.1, fill=c)
    text(s, x + 0.18, 1.85, 3.5, 0.35, head, size=11.5, bold=True, color=c, font=HEAD)
    text(s, x + 0.18, 2.25, 3.5, 2.55, [(f"■  {l}", {"space_after": 3}) for l in lines], size=10.5, color="3B4A56", spacing=1.0)
text(s, 0.6, 4.95, 12, 0.3, "THE MAIN STRUCTURAL FLOW, FROM DATA TO A RESOLVED CASE", size=11.5, bold=True, color=ORANGE, font=HEAD)
flow = [("1  Prepare", "merge public datasets, one label scheme"), ("2  Fine-tune", "round 1: 60 epochs, 36 min; round 2 merged data; round 3 adds the head class"), ("3  Measure", "score on held-out photos; adopt a model only if it is better"),
        ("4  Build logic", "zones, one-to-one matching, rules, penalties; tested by hand-made cases"), ("5  Ship", "detector service, API, three portals, smoke test")]
for i, (head, body) in enumerate(flow):
    x = 0.6 + i * 2.45
    rect(s, x, 5.3, 2.25, 1.5, fill=INK, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    text(s, x + 0.1, 5.35, 2.05, 0.35, head, size=13, bold=True, color=ORANGE, font=HEAD)
    text(s, x + 0.1, 5.72, 2.05, 1.05, body, size=10, color="E7EBEE", spacing=1.0)
    if i < 4:
        text(s, x + 2.2, 5.7, 0.3, 0.5, "›", size=22, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
notes(s, "Left to right: the data (all public and credited), the models and stack, and why the design is sound. Then the flow along the bottom: we fine-tuned a pretrained model rather than training from scratch, measured every candidate on photos it never saw, "
         "and only adopted a model that was better. The matching rules and penalty logic are our own code with hand-made-box tests. "
         "IF ASKED about the data: about 3,000 photos is small, so more varied site photos, especially hi-vis look-alikes and small distant workers, is our first improvement. An extra open dataset we tried was a 100% near-duplicate of our photos, so we did not count it.")

# ================================================================ 6. why it wins
s = base("Why SiteGuard wins", "Accuracy you can check, and a product you can use today")
stats = [("0.876", "mean detection score on 314 unseen photos", INK), ("0.941", "helmet detection score (person 0.925, vest 0.901)", GOOD),
         ("91.8%", "of 'no helmet' flags were right", GOOD), ("95.8%", "of no-helmet workers flagged or sent for review", GOOD)]
for i, (num, label, c) in enumerate(stats):
    x, y = 0.6 + (i % 2) * 2.95, 1.7 + (i // 2) * 1.6
    rect(s, x, y, 2.8, 1.45, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 1.45, fill=c)
    text(s, x + 0.25, y + 0.03, 2.45, 0.8, num, size=38, bold=True, color=c, font=HEAD)
    text(s, x + 0.25, y + 0.8, 2.45, 0.65, label, size=11.5, color="3B4A56", spacing=1.0)
text(s, 0.6, 4.95, 5.8, 0.9, "Also measured: night model precision 0.890; 69% of missing vests caught automatically; second model held back 0 of 88 real violations; every figure re-runnable from a script.",
     size=11, color=GREY, spacing=1.02)
text(s, 6.7, 1.65, 6, 0.35, "WHY JUDGES SHOULD PICK SITEGUARD", size=12, bold=True, color=ORANGE, font=HEAD)
why = [("It answers the hard part of the brief.", "A helmet anywhere never clears everyone: each item belongs to one worker."),
       ("It is fair.", "Unsure cases go to review, and a person confirms every violation and approves every penalty."),
       ("It is a whole product.", "Camera to supervisor to employee, with a PDF notice showing the exact fault and pictures."),
       ("It is measured.", "Scores on unseen photos, tuned with reasons, with a night model for dark sites."),
       ("It does more than asked.", "Live camera, worker-down alert, falling-object and welding watches, sector gear rules.")]
for i, (a, b) in enumerate(why):
    y = 2.0 + i * 0.8
    rect(s, 6.7, y, 6.0, 0.74, fill=CARD, line=LINE)
    rect(s, 6.7, y, 0.08, 0.74, fill=ORANGE)
    text(s, 6.9, y + 0.01, 5.7, 0.3, a, size=12.5, bold=True, font=HEAD)
    text(s, 6.9, y + 0.3, 5.75, 0.44, b, size=10, color="3B4A56", spacing=0.98)
rect(s, 0.6, 6.0, 12.1, 0.8, fill=INK)
text(s, 0.85, 6.0, 11.6, 0.8, "A supervisor cannot watch everyone. SiteGuard watches every worker, says exactly what is missing, and leaves the decision to a person.", size=15, bold=True, color="FFFFFF", anchor=MSO_ANCHOR.MIDDLE)
notes(s, "This is the selling slide. Left: the proof, all measured on photos the model never saw (scripts/compare_models.py and scripts/eval_workers.py, re-run on the morning of the demo). "
         "Right: five reasons to pick us, in order of how much they matter to a judge. Finish on the ribbon. "
         "IF A JUDGE ASKS about limits, answer plainly: about 12.9% of labelled workers are not found (small or hidden), hi-vis shirts and life jackets can pass as vests, backlit workers can be wrongly flagged (most go to review), "
         "faces under about 48 px are not recognised, and the live camera has not yet been tried on a physical camera. We do not claim 99.99%; no honest system can. Then say what is next: more hard-negative photos and a real-site pilot.")

# ================================================================ 7. examples
s = base("See it in action: real examples", "From the test photos")
for i, (name, cap) in enumerate([("hand.jpg", "Helmets in hands: workers flagged, helmets shown as unassigned"), ("table.jpg", "A helmet on a table clears nobody"), ("crowd.jpg", "A busy site: each worker judged, amber = a person checks")]):
    x = 0.6 + i * 2.85
    picture(s, name, x, 1.65, h=3.6)
    text(s, x - 0.05, 5.3, 2.75, 0.55, cap, size=10, color=GREY, align=PP_ALIGN.CENTER, spacing=0.98)
picture(s, "nopp.jpg", 9.4, 1.65, w=3.3)
text(s, 9.4, 3.92, 3.3, 0.45, "No helmet, no vest: red, with the missing items named", size=10, color=GREY, align=PP_ALIGN.CENTER, spacing=0.98)
picture(s, "clean.jpg", 9.4, 4.5, w=3.3)
text(s, 9.4, 6.4, 3.3, 0.3, "Fully equipped, near or far: green OK", size=10, color=GREY, align=PP_ALIGN.CENTER)
rect(s, 0.6, 5.95, 8.3, 0.9, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.8, 5.95, 7.95, 0.9, "One system from camera to resolved case: caught, named, reviewed by a supervisor, penalty proposed, PDF notice with the exact fault, and the employee can dispute it.", size=12.5, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.02)
notes(s, "These are real outputs on our test photos. Left to right: helmets in hands (the workers are flagged and the helmets are shown as unassigned, which answers the brief's hard constraint), a helmet on a table, and a busy site where unsure workers are amber for a person to check. "
         "On the right: no helmet and no vest in red with the items named, and a fully equipped worker in green. The bottom box is the whole chain in one line. "
         "If you have time, switch to the live demo: demo desk, then the supervisor panel case, then the employee portal and the PDF notice.")

# ================================================================ 8. thank you
s = prs.slides.add_slide(BLANK)
counter["n"] += 1
background(s, INK)
stripe(s, 0, 0.3)
stripe(s, H - 0.3, 0.3)
text(s, 0.9, 1.3, 11.5, 1.3, "THANK YOU", size=72, color="FFFFFF", bold=True, font=HEAD)
rect(s, 0.9, 3.0, 0.08, 1.45, fill=ORANGE)
text(s, 1.15, 2.95, 11.2, 1.6, "“Every worker. Every item. One at a time.”", size=34, color=ORANGE, font=HEAD)
text(s, 1.15, 3.75, 11.2, 0.9, "SiteGuard checks each worker for the gear they should wear, says exactly what is missing,\nand lets a person make the final call.", size=18, color="E7EBEE", spacing=1.12)
rect(s, 0.9, 5.05, 4.6, 0.62, fill=ID_CHIP, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 0.9, 5.05, 4.6, 0.62, "TEAM  HF27-0030", size=22, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 5.8, 5.05, 6.8, 0.62, "Questions are welcome.", size=22, color="FFFFFF", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.9, 5.98, 6, 0.3, "TEAM MEMBERS", size=11, bold=True, color=YELLOW, font=HEAD)
member_chips(s, 0.9, 6.28, w=2.2, h=0.46)
text(s, 0.9, 6.82, 11.5, 0.3, "KLS Vishwanathrao Deshpande Institute of Technology, Haliyal   |   CSE & CSE (AI & ML)", size=11, color="9AA6B0")
notes(s, "Close with the line and thank the judges. If asked what is built versus planned: slides 3 and 7 are built and working today; the roadmap is a real-site pilot, more training photos from real sites, and real accounts, consent and hosting.")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
