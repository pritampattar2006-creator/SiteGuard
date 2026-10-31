# SiteGuard: the modules, what each one does, and how well it works

Each module has one job, a file or two, tests, and (where it can be measured) a number. Numbers come from scripts in `scripts/` that can be re-run. A blank in the "measured" column means we have **not** measured it. Full detail: `ACCURACY_MEASURED.md`.

## A. The detector (Python, folder `ppe-detection`)

| # | Module | Job | Files | Tests | Measured |
|---|---|---|---|---|---|
| 1 | **Find people and gear** | Detect person, helmet, vest and bare head; zoomed tiles for small workers; a second, night-trained model used only for dark pictures | `ppe/detector.py`, `config.py`, `types.py`, `geometry.py` | `test_tiling`, `test_fuse` | AP50 on 314 held-out photos: person 0.925, helmet 0.941, vest 0.901, head 0.736 (mean 0.876). Missing vest: 54 of 78 caught automatically (69%), 17 more sent to review |
| 2 | **Per-worker rules** | Give each helmet and vest to exactly one worker, then decide COMPLIANT / VIOLATION / NEEDS REVIEW and name what is missing | `associate.py`, `rules.py`, `pipeline.py` | `test_associate`, `test_rules`, `test_pipeline` | "No helmet" precision 0.918, recall 0.812 (0.958 counting "review"); 12.9% of labelled workers never found |
| 3 | **Object check** | A "person" box that holds no body (a crane's concrete bucket) is marked an object and never flagged | `verify.py` | `test_verify` | Works on the crane clip; false-rejection rate of real workers not measured |
| 4 | **Second-model cross-check** | A helmet call is held back for review if a second model sees a helmet | `crosscheck.py` | `test_crosscheck` | Held back 0 of 88 real violations, caught 2 of 6 false alarms |
| 5 | **Light handling** | Brighten dark pictures; treat dark silhouettes against a bright background as "needs review"; use the night-trained model for dark pictures | `enhance.py`, `lighting.py` | `test_lighting` | Dark photos: "no helmet" precision 0.890 (was 0.647), 18.9% of workers unfound (was 22.2%). The silhouette rule moves 9 of 93 no-helmet workers from "violation" to "review" |
| 6 | **Video and falls** | Track people through a video; raise a gear incident only when it persists; a worker-down alert from body shape and an optional learned detector | `track.py`, `incident.py`, `fall_model.py` | `test_track`, `test_incident` | Learned fall detector, per clip: 53% of falls caught (24% in low light), 7% false alarms on normal clips (experimental; weak) |
| 7 | **Who is it?** | Face match for enrolled people; strict dress-colour match; otherwise a made-up name tied to that footage. A steady name across frames | `faces.py`, `people.py`, `appearance.py`, `identify.py` | `test_faces`, `test_people`, `test_appearance` | Face: no two people merged, 64 of 64 named observations right on 160 clips (4 people). Dress colours: weak, used only under a strict rule. Faces under about 48 px cannot be recognised |
| 8 | **Output** | Annotated pictures with a verdict per worker, a close-up crop of one worker, summaries | `annotate.py`, `summary.py`, `report.py`, `evidence.py` | `test_pipeline` | n/a |
| 9 | **Service** | The detector as a small web service for the sites: photo and video endpoints, sector-aware, face enrolment, people list | `detector_service.py`, `webvideo.py`, `cctv.py` | `test_cctv` (alert logic) | n/a |

Older modules from the first (Streamlit) version are kept and still tested: `roles.py` (trades), `penalties.py`, `store.py`, `service.py`, `insights.py`, `batch.py`, `ui.py`, `demo.py`.

## B. Training, measuring and test data (`scripts/`)

| Script | Job |
|---|---|
| `train.py` | Fine-tune the model (with `--lr0`, `--workers`, `--time`) |
| `make_night.py` | Darkened copies of training photos, and a darkened copy of the test photos |
| `prepare_dataset.py`, `add_chvg.py`, `prepare_head4.py`, `prepare_extras.py` | Build the training data from the public datasets (credits in `LICENSES_AND_SOURCES.md`) |
| `prepare_rf.py`, `make_vest_truth.py` | Convert an open dataset and carry its "no vest" labels onto our test photos, so the missing-vest call can be measured |
| `compare_models.py`, `eval_workers.py`, `eval_crosscheck.py` | The measurements. `eval_workers.py --dataset ppe4 / ppe4_night / ppe4_vest` |
| `build_test_cases.py`, `fetch_lookalikes.py` | The test-case folders on the Desktop and their outputs |
| `make_roster.py`, `enroll_folder.py`, `cctv.py` | Made-up employees, bulk face enrolment, a CCTV-style watcher |

## C. The web system (folder `siteguard-web`)

| # | Module | Job | Files | Tests |
|---|---|---|---|---|
| 10 | **API: cases** | Take what the detector found; one violation per person per day; remarks; notify the employee at once | `api/src/app.js`, `daily.js`, `remarks.js` | `flow.test.js` |
| 11 | **API: sectors and supervisors** | Kinds of work, each with its own required gear and its own supervisors; supervisors see only their own sector | `app.js`, `seed.js` | `flow.test.js`, `seed.test.js` |
| 12 | **API: penalties and pay** | Three confirmed violations in 30 days propose a penalty a supervisor must approve; pay view | `policy.js`, `salary.js` | `flow.test.js` |
| 13 | **Supervisor panel** | Overview, review queue, cases, penalties, employees, sectors and supervisors, face matching | `supervisor-site/src/*` | `desk.render.test.mjs` covers shared screens |
| 14 | **Employee portal** | Personal feed, violations, salary, penalties | `employee-site/src/*` | smoke test |
| 15 | **Demo desk** | One sector menu and one upload button for photos or videos, a live camera, spoken alerts | `feed-site/src/App.jsx`, `shared/detect.jsx`, `shared/alerts.js` | `alerts.test.js`, `desk.render.test.mjs` |
| 16 | **Smoke test** | Walks one case through the whole system | `scripts/smoke.mjs` | `npm run smoke` |

## D. What is not measured or not possible

- The live camera on a real camera, and the spoken alerts by ear.
- Gloves, boots and goggles (second model, accuracy unknown).
- Hi-vis shirts and life jackets: shown in the test cases, but no labelled photos exist to train on.
- A heart attack as such, or something falling on a worker: a camera can only say a worker is down.
- A real accuracy figure of 99.99%: not claimed, and not possible to claim honestly.

## E. Added later: extra watches (Python, folder `ppe-detection`)

| Module | Job | Files | Tests | Measured |
|---|---|---|---|---|
| **Falling-object watch** | On a fixed camera, follow large areas that keep dropping; log them, or alarm when one is near or overlaps a worker | `ppe/hazard.py` | `test_hazard` | Only checked on the test clips; a handheld or moving camera breaks it |
| **Welding watch** | A tiny, bright, flickering flash with sparks next to a worker is reported as "welding seen" for a supervisor to check; it is not a violation | `ppe/welding.py` | `test_welding` | Synthetic frames only; not measured on real welding footage |
| **Live camera** | Read a phone or CCTV stream, keep the newest frame, analyse about once a second | `ppe/livefeed.py` | `test_livefeed` | Not tried with a physical camera |
