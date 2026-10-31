# SiteGuard

**PPE compliance monitoring for industrial and construction sites.** SiteGuard checks each worker in a photo, a video or a live camera for the safety gear their trade requires, names what is missing, and routes every catch to a supervisor who decides. Repeat violations follow a fair, documented penalty and escalation process.

Built for hackathon HF27-0030.

> A helmet detected anywhere in the image must not mean every worker is compliant. SiteGuard matches every helmet and vest to the person wearing it, and each item belongs to at most one worker.

## What is in this repository

| Folder | What it is | Stack |
|---|---|---|
| [`ppe-detection/`](ppe-detection) | Detection engine: people, helmets, vests, bare heads, gloves, boots, goggles; worker tracking; face and people registry; penalty rules; detector HTTP service (`:5000`) | Python, YOLO11, OpenCV, PyTorch, Streamlit |
| [`siteguard-web/`](siteguard-web) | Web product: API (`:4000`), supervisor panel (`:3002`), employee portal (`:3001`) and demo desk (`:3003`) | Node, Express, React, Vite |

## How it works

1. A photo, video or live camera frame goes to the detector. Every worker is checked against the gear required for their sector.
2. Each worker who broke a rule is sent to the supervisor with the picture and a short remark written from the facts of the case.
3. The employee is alerted straight away, but it becomes a **violation** only when a supervisor confirms it. A person always makes the final decision.
4. At most one violation per person per day. Three confirmed violations in 30 days propose a penalty, which a supervisor must approve and the employee can dispute.

## Quick start (Windows)

Detector (see [`ppe-detection/README.md`](ppe-detection/README.md) for the full setup, including the CUDA build of PyTorch and the model weights):

```powershell
cd ppe-detection
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
```

Web (see [`siteguard-web/README.md`](siteguard-web/README.md)):

```powershell
cd siteguard-web
npm install
npm run start:all      # API, the three sites and the detector together
npm run smoke          # checks every service and walks one case through the flow
```

Model weights, datasets, run outputs and face templates are **not** in this repository (see `.gitignore` in each folder). Without `weights/best.pt` the detector will not start.

## Measured results, and their limits

On 314 held-out photos the current model scores AP50 of 0.925 for person, 0.941 for helmet, 0.901 for vest and 0.736 for bare head (mean 0.876). The learned fall detector is weak and off by default. Every figure, how it was measured and what was **not** measured is in [`ppe-detection/docs/ACCURACY_MEASURED.md`](ppe-detection/docs/ACCURACY_MEASURED.md). No accuracy beyond those numbers is claimed.

Known limits: the system does not see why a worker is down, can mistake hi-vis shirts and life jackets for vests, and can miss small or hidden workers. Live camera has been tested against a stand-in video stream, not yet a physical camera.

## Demo data and security

All names, salaries, penalty amounts and passwords in the demo are made up. The demo sites can sign themselves in as demo accounts; **turn real login back on and change every demo password before any public deployment.**

## Licences and credits

Uses Ultralytics YOLO11 (AGPL-3.0), the Construction-PPE dataset (AGPL-3.0), CHVG (CC BY 4.0) and GMDCSA24 (MIT), plus OpenCV, PyTorch, Streamlit, ReportLab and others. Weights trained on these datasets inherit their terms. Full list: [`ppe-detection/docs/LICENSES_AND_SOURCES.md`](ppe-detection/docs/LICENSES_AND_SOURCES.md). No `LICENSE` file has been chosen for this repository yet.

Written for this project with Claude (Anthropic) as a coding assistant; the team reviews the work.
