"""The 8-slide SiteGuard pitch deck (Team HF27-0030): everything that was built, in eight slides.

  python docs/deck/build_deck_8.py docs/deck docs/SiteGuard_Pitch_HF27-0030_8slides.pptx

It reuses the look (colours, fonts, helpers) of build_deck_v2.py: everything in that file before its first slide.
"""
import sys
from pathlib import Path

_src = (Path(__file__).parent / "build_deck_v2.py").read_text(encoding="utf-8")
exec(compile(_src[: _src.index("# ---------------------------------------------------------------- 1. title")], "build_deck_v2_prelude", "exec"))

# ---------------------------------------------------------------- 1. title
s = prs.slides.add_slide(BLANK)
background(s, INK)
stripe(s, 0, 0.3)
stripe(s, H - 0.3, 0.3)
text(s, 0.9, 1.35, 11.5, 0.4, "KLS VISHWANATHRAO DESHPANDE INSTITUTE OF TECHNOLOGY, HALIYAL", size=13, color=YELLOW, bold=True, font=HEAD)
text(s, 0.9, 1.7, 9, 0.35, "Department of CSE & CSE (AI & ML)   |   Theme: Computer Vision", size=13, color="C8D0D6")
text(s, 0.9, 2.45, 11.5, 1.2, "SITEGUARD", size=72, color="FFFFFF", bold=True, font=HEAD)
text(s, 0.9, 3.6, 11.5, 0.8, "PPE Compliance Detection", size=36, color=ORANGE, font=HEAD)
text(s, 0.9, 4.5, 11, 0.9, "We don't ask if a helmet is in the picture.\nWe ask whose head it is on.", size=22, color="E7EBEE", spacing=1.1)
rect(s, 0.9, 5.75, 4.6, 0.62, fill=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 0.9, 5.75, 4.6, 0.62, "TEAM ID: HF27-0030", size=22, color=INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 5.8, 5.75, 6.5, 0.62, "Problem Statement 1  |  Computer Vision", size=18, color="C8D0D6", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.9, 6.55, 11, 0.35, "Team members: [Name 1]   [Name 2]   [Name 3]   [Name 4]", size=13, color="9AA6B0")
notes(s, "Introduce the team (ID HF27-0030) and the project in one sentence: SiteGuard checks every worker in a photo, a video or a live camera for the protective equipment they should wear, "
         "says exactly what is missing, and lets a supervisor and the worker see it. The tagline is the core idea: each helmet and vest is matched to the worker wearing it. Fill in the team names on this slide.")

# ---------------------------------------------------------------- 2. problem and idea
s = base("The problem and our idea", "Problem Statement 1")
rect(s, 0.6, 1.75, 5.2, 2.55, fill=INK)
text(s, 0.85, 1.9, 4.75, 2.3, [("“Supervisors cannot consistently spot workers without helmets or safety vests across busy industrial areas.”", {"size": 19, "color": "FFFFFF", "font": HEAD})], spacing=1.1)
text(s, 0.6, 4.45, 5.2, 1.2, [("Objective", {"bold": True, "color": ORANGE, "size": 13}),
                              "Detect each worker, decide whether that worker wears the required equipment, flag violations, show annotated pictures and a summary."],
     size=13.5, color="3B4A56", spacing=1.05)
ideas = [("Per worker, not per picture", "Every helmet and vest is matched to the one worker wearing it, by head and torso zone. A helmet in a hand or on a table clears nobody.", ORANGE),
         ("Three outcomes, not two", "GREEN ok. RED violation, with the missing item named. AMBER needs review: it cannot judge fairly, so a person looks instead of someone being accused.", BLUE),
         ("A person decides", "Nothing is a violation until a supervisor confirms it, and a penalty is only ever proposed. The worker can dispute it.", GOOD)]
for i, (head, body, c) in enumerate(ideas):
    y = 1.75 + i * 1.62
    rect(s, 6.1, y, 6.6, 1.5, fill=CARD, line=LINE)
    rect(s, 6.1, y, 0.09, 1.5, fill=c)
    text(s, 6.35, y + 0.08, 6.2, 0.4, head, size=16, bold=True, font=HEAD)
    text(s, 6.35, y + 0.52, 6.2, 0.98, body, size=12.5, color="3B4A56", spacing=1.03)
rect(s, 0.6, 6.05, 12.1, 0.7, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 6.05, 11.6, 0.7, "Constraint from the problem statement: a helmet detected anywhere in the image must not mean every worker in it is compliant.", size=15, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Read the problem statement as given. The last line is the heart of it: a model that only asks 'is there a helmet in this picture?' would clear everyone. "
         "Our three ideas answer it: match gear to the worker, say 'needs review' when unsure, and keep a human in charge of every violation and penalty.")

# ---------------------------------------------------------------- 3. how it works
s = base("How it works", "Six steps, one AI model")
chips = [("1", "Brighten", "dark photos", "ENHANCE", INK), ("2", "Detect", "person, helmet, vest, head", "AI MODEL", ORANGE), ("3", "Match", "each item to one worker", "OUR LOGIC", INK),
         ("4", "Judge", "rules for that worker's trade", "OUR LOGIC", INK), ("5", "Check", "object test, second model", "OUR LOGIC", INK), ("6", "Report", "picture, case, notice", "OUR CODE", INK)]
for i, (n, head, sub, tag, c) in enumerate(chips):
    x = 0.6 + i * 2.05
    rect(s, x, 1.75, 1.9, 1.75, fill=CARD, line=ORANGE if tag == "AI MODEL" else LINE, line_w=2 if tag == "AI MODEL" else 1)
    text(s, x + 0.12, 1.8, 0.6, 0.5, n, size=22, bold=True, color=ORANGE, font=HEAD)
    text(s, x + 0.12, 2.28, 1.7, 0.4, head, size=16, bold=True, font=HEAD)
    text(s, x + 0.12, 2.65, 1.7, 0.55, sub, size=10.5, color=GREY, spacing=1.0)
    text(s, x + 0.12, 3.2, 1.7, 0.25, tag, size=9, bold=True, color=ORANGE if tag == "AI MODEL" else GREY)
text(s, 0.6, 3.75, 12, 0.4, "HARD CONDITIONS FROM THE PROBLEM STATEMENT, AND WHAT HANDLES THEM", size=12, bold=True, color=ORANGE, font=HEAD)
hard = [("Poor light", "Brightened first, and a night-trained model is used only when the picture is dark."),
        ("Distance", "A larger input size plus zoomed tiles find small workers."),
        ("Crowds and hiding", "Cut-off, crowded or backlit workers go to 'needs review', not 'violation'."),
        ("False alarms", "An object test (a crane bucket is not a worker) and a second model double-check every helmet call.")]
for i, (head, body) in enumerate(hard):
    card(s, 0.6 + i * 3.07, 4.2, 2.9, 2.35, head, body, accent=[BLUE, GOOD, WARN, BAD][i], head_size=15, body_size=12)
text(s, 0.6, 6.62, 12, 0.3, "Only step 2 uses the AI model (YOLO11, fine-tuned). Everything else is logic we wrote and tested.", size=11.5, color=GREY)
notes(s, "Walk the six steps left to right and stress that only step 2 is the AI model; the matching, rules, checks and reports are our own logic. "
         "Then the four cards: each one answers a hard condition in the problem statement. The key trick for crowds and hiding is that we say 'needs review' instead of accusing.")

# ---------------------------------------------------------------- 4. results
s = base("Why you can trust it: measured, not claimed", "Tested on photos the model never saw")
stats = [("0.876", "mean detection score (mAP50) on 314 held-out photos", INK), ("91.8%", "of people flagged for no helmet really had none (precision)", GOOD),
         ("95.8%", "of no-helmet workers flagged or sent to a person to review", GOOD), ("0.890", "no-helmet precision in dark photos with our night model (0.647 without it)", GOOD)]
for i, (num, label, c) in enumerate(stats):
    x, y = 0.6 + (i % 2) * 3.0, 1.75 + (i // 2) * 1.85
    rect(s, x, y, 2.8, 1.65, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 1.65, fill=c)
    text(s, x + 0.25, y + 0.05, 2.4, 0.85, num, size=42, bold=True, color=c, font=HEAD)
    text(s, x + 0.25, y + 0.9, 2.45, 0.75, label, size=12, color="3B4A56", spacing=1.0)
picture(s, "clean.jpg", 6.8, 1.75, w=5.9)
text(s, 6.8, 5.05, 5.9, 0.4, "A fully equipped worker and a distant one: both OK", size=12, color=GREY, align=PP_ALIGN.CENTER)
rect(s, 0.6, 5.5, 12.1, 1.15, fill=SOFT, line=YELLOW, line_w=2)
text(s, 0.85, 5.5, 11.6, 1.15, "Per class: person 0.925, helmet 0.941, vest 0.901, bare head 0.736. Missing vests: 69% caught automatically and more sent to review. "
                                 "A second model double-checks every helmet call: it held back none of 88 real violations. Every number comes from a script anyone can re-run.", size=12.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
notes(s, "Every number here comes from a script in the project that can be re-run (scripts/compare_models.py for the detection score and scripts/eval_workers.py for the per-worker verdicts), "
         "and the detection score was re-run on the morning of the demo. Lead with the strengths: 0.941 for helmets, 91.8% precision, and the dark-photo result from the night model. "
         "IF A JUDGE ASKS about limits, answer plainly and do not dodge: about 12.9% of labelled workers were not found (small or hidden ones), and we do not claim 99.99%, because no honest system can. "
         "Of 661 labelled workers, 78 no-helmet workers were caught, 7 helmet-wearers wrongly flagged, 4 missed and 14 sent to review.")

# ---------------------------------------------------------------- 5. what we built
s = base("What we built: three portals, one API", "A working system, not just a model")
cols = [("Demo desk", ORANGE, ["Photo, video or a live phone camera", "The sector chosen sets the gear required", "Live picture turns itself upright (and has a Rotate button)", "Spoken alert only for people who broke a rule"]),
        ("Supervisor panel", BLUE, ["Review queue: the exact fault, picture, auto-written remark", "Confirm or dismiss each catch against a named employee", "Put a penalty on an employee ID, approve or waive proposals", "Cases with a PDF notice, accident alerts, face enrolment"]),
        ("Employee portal", GOOD, ["Own feed: the exact fault and both pictures", "Download the violation notice as a PDF", "Acknowledge or dispute with a reason", "Salary view with penalties; safety alerts"])]
for i, (head, c, lines) in enumerate(cols):
    x = 0.6 + i * 4.1
    rect(s, x, 1.75, 3.8, 3.55, fill=CARD, line=LINE)
    rect(s, x, 1.75, 3.8, 0.1, fill=c)
    text(s, x + 0.2, 1.95, 3.4, 0.45, head, size=18, bold=True, font=HEAD)
    text(s, x + 0.2, 2.5, 3.45, 2.8, [(f"■  {l}", {"space_after": 6}) for l in lines], size=12.5, color="3B4A56", spacing=1.03)
flow = [("Detector", "Python, port 5000"), ("API", "Node, port 4000"), ("Supervisor", "port 3002"), ("Employee", "port 3001")]
for i, (a, b) in enumerate(flow):
    x = 0.6 + i * 3.1
    rect(s, x, 5.55, 2.7, 0.75, fill=INK, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.15)
    text(s, x, 5.57, 2.7, 0.4, a, size=15, bold=True, color="FFFFFF", font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x, 5.92, 2.7, 0.3, b, size=10.5, color="C8D0D6", align=PP_ALIGN.CENTER)
    if i < 3:
        text(s, x + 2.65, 5.58, 0.5, 0.65, "→", size=26, bold=True, color=ORANGE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 6.45, 12.1, 0.45, "Also built: a Streamlit app with Supervisor, Worker and Authority pages (trades, ten-rule library, escalation to the authority). Accounts and names are made up for the demo.", size=11.5, color=GREY)
notes(s, "This is the product, not just the model. Follow one catch: the desk sends a picture to the detector, the case goes to the API and the supervisor's review queue, the supervisor confirms it against a named employee, "
         "and the employee sees it in their own portal with the exact fault and can download the PDF notice. Demo logins: S001 and E001, password 123456789. "
         "If asked about the Streamlit app: it is the earlier three-page interface with trades and authority escalation.")

# ---------------------------------------------------------------- 6. fairness and notice
s = base("Fair penalties, and a notice that shows the fault", "A person decides")
rules = [("One violation per person per day", "Caught again the same day: only the count goes up."),
         ("Three confirmed in 30 days", "The system PROPOSES a penalty (example INR 500). A supervisor approves or waives it."),
         ("Or the supervisor puts one", "Enter an employee ID with confirmed violations, choose the violations and amount, issue it."),
         ("The worker can dispute", "With a written reason. In the Streamlit app, repeat cases also escalate to the authority."),
         ("Dismissed never counts", "A false alarm does not count against anyone.")]
for i, (head, body) in enumerate(rules):
    y = 1.75 + i * 0.98
    rect(s, 0.6, y, 6.4, 0.88, fill=CARD, line=LINE)
    rect(s, 0.6, y, 0.09, 0.88, fill=[ORANGE, BLUE, BAD, WARN, GOOD][i])
    text(s, 0.85, y + 0.04, 6.0, 0.35, head, size=14, bold=True, font=HEAD)
    text(s, 0.85, y + 0.4, 6.05, 0.48, body, size=11.5, color="3B4A56", spacing=1.0)
picture(s, "notice.png", 7.7, 1.7, h=4.75)
text(s, 7.3, 6.5, 5.7, 0.4, "Violation notice (PDF): the exact fault and both pictures", size=11.5, color=GREY, align=PP_ALIGN.CENTER)
text(s, 0.6, 6.7, 6.5, 0.3, "Amounts are examples; management and HR set the real ones.", size=10.5, color=GREY)
notes(s, "Fairness is the point of this slide. Nothing is automatic: the system proposes, a supervisor decides, the worker can dispute. A supervisor can also put a penalty directly on an employee ID, "
         "but only one that has confirmed violations not yet covered by a penalty. On the right is the one-page violation notice: the exact fault in large red text, the employee, time and place, "
         "the close-up and the whole picture. The employee downloads it in their portal and the supervisor from the cases table. All amounts are examples.")

# ---------------------------------------------------------------- 7. extras
s = base("More than the brief asked for", "Built beyond helmets and vests")
extras = [("Worker-down alert", "Tells a supervisor when someone goes down and stays still, with a siren in the panel and an accident report.", GOOD),
          ("Falling-object watch", "Follows large objects dropping on a fixed camera and alerts when one comes near or hits a worker.", GOOD),
          ("Welding watch", "Spots welding flashes next to a worker and prompts a supervisor to check the shield and gloves.", GOOD),
          ("Live phone or CCTV camera", "Watches a camera stream continuously, turns the picture upright by itself, and sends catches to the supervisor.", GOOD),
          ("Naming with consent", "Matches a face only for employees who agreed, and keeps just a numeric template, never the photo.", GOOD),
          ("Gloves, boots, goggles", "Each sector sets its own required gear: construction, lineman, wireman and welding all differ.", GOOD)]
for i, (head, body, c) in enumerate(extras):
    x, y = 0.6 + (i % 3) * 4.1, 1.75 + (i // 3) * 2.4
    rect(s, x, y, 3.8, 2.2, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 2.2, fill=c)
    text(s, x + 0.25, y + 0.1, 3.4, 0.4, head, size=15, bold=True, font=HEAD)
    text(s, x + 0.25, y + 0.62, 3.4, 1.55, body, size=12.5, color="3B4A56", spacing=1.05)
text(s, 0.6, 6.55, 12.1, 0.35, "Every alert asks a person to look. None of them records a violation or a penalty by itself.", size=12, bold=True, color=INK)
notes(s, "These go beyond the problem statement and show the system is a safety platform, not just a detector. The design rule for all of them: an alert asks a person to look, and never creates a violation or a penalty by itself. "
         "IF A JUDGE ASKS how well they work, be exact: the falling-object and welding watches use motion and brightness rules and were checked on test clips and synthetic frames; "
         "the live camera was tried on a stand-in video stream and not yet on a physical camera; the learned fall detector caught 53% of acted falls with 7% false alarms per clip (24% caught in low light); "
         "face naming gave 64 of 64 correct observations on 160 clips but cannot work on faces under about 48 px; gloves, boots and goggles accuracy has not been measured. "
         "Never describe any of these as reliable.")

# ---------------------------------------------------------------- 8. why we win
s = base("Why SiteGuard wins", "What makes it different")
wins = [("Solves the hard constraint", "A helmet anywhere in the picture never clears everyone: each item is matched to the one worker wearing it.", ORANGE),
        ("Every verdict has a reason", "Green, red or amber for each worker, naming exactly what is missing, in plain words a supervisor can check.", BLUE),
        ("Fair by design", "Weak evidence goes to review, not to accusation. A person confirms every violation and approves every penalty.", GOOD),
        ("A complete product", "Detector, supervisor panel, employee portal and a PDF notice with the exact fault and its pictures: caught to resolved.", ORANGE),
        ("Measured and reproducible", "Scores on unseen photos, a night-trained model for dark scenes, a second model checking every helmet call.", BLUE),
        ("Goes beyond the brief", "Live phone camera, worker-down, falling-object and welding watches, and sector-specific gear rules.", GOOD)]
for i, (head, body, c) in enumerate(wins):
    x, y = 0.6 + (i % 3) * 4.1, 1.65 + (i // 3) * 1.95
    rect(s, x, y, 3.8, 1.8, fill=CARD, line=LINE)
    rect(s, x, y, 0.09, 1.8, fill=c)
    text(s, x + 0.25, y + 0.08, 3.45, 0.4, head, size=15, bold=True, font=HEAD)
    text(s, x + 0.25, y + 0.55, 3.45, 1.25, body, size=12, color="3B4A56", spacing=1.03)
text(s, 0.6, 5.55, 12.1, 0.3, "BUILT WITH", size=11, bold=True, color=ORANGE, font=HEAD)
text(s, 0.6, 5.8, 12.1, 0.35, "Python, YOLO11, PyTorch, OpenCV   |   Node.js, Express, React   |   279 Python + 37 API tests and an end-to-end smoke test   |   two public datasets, credited", size=11.5, color=GREY)
rect(s, 0.6, 6.2, 12.1, 0.75, fill=INK)
text(s, 0.85, 6.2, 8.4, 0.75, "Every worker. Every item. One at a time.", size=22, bold=True, color=ORANGE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 9.6, 6.32, 2.9, 0.52, fill=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
text(s, 9.6, 6.32, 2.9, 0.52, "TEAM HF27-0030", size=16, bold=True, color=INK, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Finish on the six reasons it wins, then the closing line. Our roadmap is a pilot on a real site camera, more training photos from real sites, and real accounts, consent and hosting. "
         "IF A JUDGE ASKS where it still fails, answer plainly: about 12.9% of labelled workers are not found (small or hidden), hi-vis shirts and life jackets can pass as vests, backlit workers can be wrongly flagged "
         "(most go to review), faces under about 48 px cannot be recognised, and the live camera has not been tried on a physical camera. Then say what you would do about it: more hard-negative photos and a real-site pilot. "
         "Thank the judges and invite questions.")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
