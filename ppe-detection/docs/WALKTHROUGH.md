# Walkthrough: how each module works and why

Plain-language notes so the team can explain every part to the judges.

| Module | What it does | Why it is built this way |
|---|---|---|
| `ppe/types.py` | Small data classes (`Detection`, `WorkerMatch`, `Verdict`, `AnalysisResult`) | Modules only pass these objects to each other, so each one can be tested alone |
| `ppe/geometry.py` | Box maths: area, overlap, "how much of A is inside B" | Pure functions, no model needed, easy to unit-test |
| `ppe/config.py` | Every tunable number in one place | Tuning thresholds never means hunting through code |
| `ppe/detector.py` | Wraps the YOLO model. Matches classes **by name**, not by number. Keeps weak detections down to a floor | Different datasets number their classes differently. Weak detections are still useful evidence (see rules) |
| `ppe/enhance.py` | Detects dark photos and boosts contrast (CLAHE) on the lightness channel only | Helps poor lighting without changing the colour of a vest |
| `ppe/associate.py` | **The core.** Gives each helmet to the worker whose head zone it sits in, each vest to the worker whose torso it covers, one-to-one | Answers the constraint: a helmet somewhere in the image must not clear everyone. A helmet in a hand or on a table is in nobody's head zone |
| `ppe/rules.py` | Turns a worker's matches into COMPLIANT / VIOLATION / NEEDS_REVIEW with a reason sentence | Small, cut-off, crowded or borderline workers are sent to review instead of being wrongly accused |
| `ppe/pipeline.py` | Glue: enhance, detect, associate, rules | No logic of its own, so tests can pass a fake detector |
| `ppe/annotate.py` | Draws green / red / amber boxes and labels that do not overlap in crowds | A verdict has to be readable on the image |
| `ppe/summary.py` | Per-worker table, counts, breakdown by missing item, CSV and JSON | The violation summary requirement |
| `ppe/batch.py` | Analyses a whole folder (optionally watching it) and writes an HTML report | Automatic analysis of many images |
| `ppe/track.py` | Follows each worker across video frames. Reports a violation only after it persists (5 of the last 8 usable frames) | Stops one-frame flicker from raising alarms |
| `eval/run_eval.py` | Scores the system against a hand-written answer key, by hard-case group | Honest accuracy, including failures |
| `app.py`, `pages/1_Video.py` | Streamlit web app for photos and video | Layout only, all decisions live in `ppe/` |

## Added later

| Module | What it does | Why it is built this way |
|---|---|---|
| `ppe/roles.py` + `config/ppe_rules.json` | Reads which equipment each job role must wear from an editable file | The safety officer, not the code, decides the rules. Unknown items or empty roles are rejected with a plain message |
| `ppe/incident.py` | Watches each tracked person's box over time. A person who goes from upright to lying within about a second and stays still for 3 s raises a **worker down** alert (kind FALL). Someone already lying when first seen needs 5 s (kind DOWN) | A lying person's box is much wider than tall. It cannot say *why* someone is down, so an alert means "check now", not a diagnosis |
| `ppe/associate.py` (bare head) | If a `head` (bare or covered head) is more convincing than a "helmet" on the same head, the helmet is cancelled and the worker is a clear NO HELMET | A cap, beanie or head cloth that the model reads as a helmet now has a competing explanation |
| `ppe/store.py`, `service.py`, `report.py` | Violation register (SQLite), saving violations with evidence, PDF notices | Every case has a time log, a status and a named worker once a supervisor assigns one |
| `ppe/detector.py` (second model, ensemble) | Optional second model for gloves, boots and goggles, and an experimental ensemble mode | The ensemble can agree on a mistake (a beanie), so it is not the default |

## Three ideas worth remembering
1. **Missing is inferred, not detected.** We do not train a "no helmet" class. If no helmet is matched to a worker's head zone, they are missing one.
2. **Three outcomes, not two.** NEEDS_REVIEW exists so the system never accuses a worker it cannot actually see properly.
3. **Weak evidence blocks an accusation.** A helmet seen with low confidence on a worker's head sends them to review rather than flagging a violation.
