# SiteGuard: PPE compliance, penalties and escalation for construction sites

Supervisors cannot consistently spot workers without helmets or safety vests across busy industrial areas. SiteGuard checks **each worker** in a photo, a video or a live camera
for the equipment their trade requires, names what is missing, keeps a record, and runs a fair repeat-violation process: worker, supervisor, and the authority above them.

**Key constraint from the problem statement:** a helmet detected anywhere in the image must not mean every worker is compliant. Every helmet and vest is
matched to the person wearing it, and each item belongs to at most one worker.

## Three pages, three levels of responsibility

| Page | For | What it does |
|---|---|---|
| **Supervisor** | Site supervisors | Check photos, video and a live camera against the worker's trade; record violations against named workers; review and **approve or waive** proposed penalties; notifications |
| **Worker** | Each worker | Sign in with an Employee ID; see violations and penalties **like a challan** (stub, amount, reason, status); acknowledge or dispute; PDF notice; safety score |
| **Authority** | The level above supervisors | Escalations to decide; **supervisor oversight** (are supervisors following the rules themselves?); site analytics; the ten rules, penalty policy and trades |

## How penalties work (example values in `config/penalty_rules.json`; management sets the real ones)
- **3 violations within 30 days** lead to a **proposed** penalty (example: INR 500). The supervisor is notified and must **approve** it before it is issued. Nothing is issued automatically.
- The worker sees it, and can **dispute** it. The supervisor is notified of the dispute.
- **5 violations** in the window also **escalate** the worker to the authority.
- **Supervisors** are held to the same rules for their own PPE. They get no money penalty here; at **2 violations** the case goes straight to the authority.
- A dismissed violation never counts. A person always makes the final decision.

## Trades and the ten rules
- `config/ppe_rules.json`: required equipment per **trade** (general labourer, mason, carpenter, scaffolder, electrician, welder, grinding/cutting, supervisor, visitor), with the tools each uses. Starter values: your safety officer must confirm them.
- `config/rules_library.json`: ten predefined rules. **Five can be checked today** (helmet, vest, boots, gloves, goggles; the last three need the second model). **Worker down** is an emergency alert, not a penalty.
  Respirator, ear protection, safety harness and restricted-zone entry are defined but **not yet detectable**, so they are never enforced.

## Features and honest status

| Feature | Status |
|---|---|
| Detect people, helmets, vests; match each item to its worker; verdict with a reason | Built, tested |
| Head class (bare or covered head): a cap or beanie is less likely to pass as a helmet | Built; helmet threshold raised to 0.35 after testing |
| Gloves, boots, goggles | Logic and model built; per-item accuracy not yet measured |
| Penalty policy, escalation, notifications, penalty and violation tickets | Built, tested (255 tests across the project) |
| Photo, video (tracking, confirmed violations, evidence frames), **live camera** | Photo and video tested. **Live camera** works against a local HTTP video stream (`scripts/live_stream_test.py`: 7 workers analysed from a stand-in stream); **not yet tested with a physical camera** |
| **Worker down** alert from body shape | Built, tested on simulated sequences |
| Learned fall detector (experimental, optional) | See below |
| Violation register, PDF notices and summaries | Built |

## What it cannot do (please read)
- **Accidents.** It can say "worker down" when someone falls or collapses and stays still. It cannot see *why*: it cannot tell a heart attack from a fall or a blow from a falling object, and it cannot see an object falling. An alert means "someone should check now".
- **The learned fall detector is weak.** Trained on 160 acted indoor falls (GMDCSA24, MIT licence, 4 people). Tested only on people it had not seen: measured per clip on 160 clips it catches **53% of falls (24% in low light) and gives a false alarm on 7% of normal clips** at the shipped setting; looser settings catch more but alarm more (see docs/ACCURACY_MEASURED.md). Off by default; treat it as weak.
- It does **not** recognise faces. A name is attached only when a supervisor assigns it.
- It treats every person it sees as a worker, so it cannot tell a visitor or passer-by from a worker, or know where PPE is required.
- Hi-vis shirts and life jackets can pass as vests. Small, background and hidden workers can be missed. A baseball cap is no longer accepted in our test photo, but caps remain a weakness.
- **No login yet.** Anyone with the app open can use any page. Do not expose it to a network. See `docs/PRIVACY_NOTES.md`.
- Penalty amounts and thresholds are **examples**; this is not an HR or legal policy.

## Run (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # CUDA 12.8 build (RTX 50-series)
python -m pip install -r requirements.txt
streamlit run app.py                                      # Supervisor, Worker, Authority
python -m ppe.pipeline --image photo.jpg --save out.png   # one image from the command line
python -m pytest                                          # all tests
```

Weights are not committed: `weights/best.pt` (person, helmet, vest, head); optional `weights/extras.pt` (gloves, boots, goggles), `weights/yolo11n-pose.pt` and `weights/fall_model.json` (learned fall detector).

```powershell
python scripts\prepare_head4.py data\raw data\extra\chvg data\ppe4
python scripts\train.py --data data\ppe4\data.yaml --model weights\best_v2.pt --epochs 25 --name ppe4
python scripts\fall_features.py <GMDCSA24 folder> data\falls\features.csv --device 0
python scripts\fall_train.py data\falls\features.csv weights\fall_model.json
```

## Results
Detection quality (mAP@50) and a by-eye review of 12 real site photos are in `docs/CASE_REVIEW.md`: on 314 held-out photos the current model (`weights/best.pt`, re-measured 31 Oct 2026 with `scripts/compare_models.py`) scores person 0.925, helmet 0.941, vest 0.901,
head 0.736 (mean 0.876). The review was by one reviewer and is indicative, not a formal benchmark.

## Licences and credits
See `docs/LICENSES_AND_SOURCES.md`. Ultralytics YOLO11 and Construction-PPE (AGPL-3.0), CHVG (Ferdous and Ahsan, 2022, CC BY 4.0), GMDCSA24 (Alam et al., 2024, MIT), OpenCV, Streamlit, pandas, NumPy,
scikit-learn, PyTorch, ReportLab, pytest. Other open-source PPE projects were read for ideas only; no code was copied. Written for this project with Claude (Anthropic) as a coding assistant; the team reviews the work.
