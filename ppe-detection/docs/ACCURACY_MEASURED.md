# What we measured, and what we did not

Every number here comes from a script in `scripts/` that can be re-run. Nothing is rounded up. **No detection system can honestly promise 99.99%.** These are the figures this one reached on photos and clips it was not trained on, unless a line says otherwise.

## 1. Finding people and gear (314 held-out photos)

`python scripts/compare_models.py weights/best_v3.pt` (AP at IoU 0.5)

| class | AP50 |
|---|---|
| person | 0.925 |
| helmet | 0.941 |
| vest | 0.901 |
| head (bare head) | 0.736 |
| **mean** | **0.876** |

## 2. Is each worker's verdict right?

Ground truth comes from the dataset's own boxes (a labelled helmet or bare head on the person's head; a labelled vest or "no vest" on the torso). Workers 60 px tall or more. `python scripts/eval_workers.py --night-weights weights/best_night.pt [--dataset ppe4 | ppe4_night | ppe4_vest]`

### Normal photos (661 labelled workers), final system

| | result |
|---|---|
| Workers the detector never found | 85 (12.9%) |
| "No helmet" caught automatically | 78 |
| "No helmet" false alarms (person wore one) | 7 |
| Missed outright | 4 |
| **Precision** of the "no helmet" call | **0.918** |
| **Recall**, automatic | **0.812** |
| Recall counting "sent to review" | 0.958 |
| Vest false alarms (person wears one) | 13 of 312 (4.2%) |

### Dark photos (the same photos darkened with brightness, gamma and noise: synthetic)

| | original model alone | final system (night-trained model for dark pictures) |
|---|---|---|
| Workers never found | 147 of 661 (22.2%) | 125 of 661 (18.9%) |
| "No helmet" precision | 0.647 | **0.890** |
| "No helmet" false alarms | 36 | 8 |
| Recall, automatic | 0.776 | 0.756 |
| Recall counting "review" | 0.988 | 0.977 |
| Vest false alarms | 19 of 289 (6.6%) | 18 of 297 (6.1%) |

Dark pictures go to a night-trained model, which accuses far fewer people wrongly (8 false alarms against 36) and finds more of the workers. Used alone on normal photos it is worse (precision 0.873, automatic recall 0.660), so it is used **only when a picture is dark**. Figures re-run on the final system for this write-up.

### Missing vests (101 test photos with a vest ground truth, 78 workers truly without a vest)

The truth comes from an open dataset's "no-vest" labels carried onto our photos (`scripts/make_vest_truth.py`). Final system: **54 caught automatically (69.2%)**, 17 more sent to review (91% flagged or reviewed), 7 missed. False alarms on people who do wear a vest: 6 of 89 (6.7%).

## 3. Safeguards, measured

| Safeguard | Result |
|---|---|
| Second-model cross-check on helmet calls | held back 0 of 88 real violations, caught 2 of 6 false alarms (a small sample) |
| Silhouette rule (backlit workers become "needs review") | the real sunset clip and all synthetic silhouettes now come out as review (5 of 5); cost: 9 of 93 no-helmet workers move from "violation" to "review". A looser first version cost 25 and was rejected |
| Object check (crane concrete bucket) | the bucket photo and clip are not flagged (2 of 2). False rejection of real workers not measured |

## 4. Worker down (falls and collapses)

`python scripts/eval_falls.py`, per **clip** (an alert needs the pattern to hold over time), 79 fall clips and 81 normal-activity clips of 4 people. The classifier was trained on windows from these same clips, so the figures are, if anything, optimistic.

| alert setting | fall clips caught (all / day / low light) | normal clips falsely alerted |
|---|---|---|
| 0.95 (shipped) | 42 of 79 (**53%**) / 61% / **24%** | 6 of 81 (7%) |
| 0.90 | 49 of 79 (62%) | 15 of 81 (19%) |
| 0.80 | 64 of 79 (81%) | 25 of 81 (31%) |

An earlier figure of "76% caught, 16% false alarms" measured short windows, not clips, and should not be used. In the Desktop test cases, 3 of 12 fall and collapse clips raised an alert. **Treat worker-down as weak, especially in low light.** It cannot tell a heart attack from a trip or a falling object.

## 5. Naming people

- **Face** (OpenCV SFace; 160 clips, 4 people): no two different people merged; 64 of 64 named observations right; each person ended with 1 or 2 names; about 20% of faces left unnamed rather than guessed. Faces narrower than about 48 px cannot be recognised (faces in crowd photos are 24 to 31 px).
- **Clothes** (`ppe/appearance.py`): weak. At a setting that wrongly links different people 0.14% of the time, only 4% of same-person pairs are recognised. Used only to recognise the same footage seen again.
- **Made-up names**: someone whose face is unclear gets a made-up name tied to that exact footage. It does not mean the system knows who they are.

## 6. Training and data notes

- A larger model (YOLO11m, about 14 epochs) scored 0.819 mean against 0.876: not used. Threshold tuning, test-time augmentation and an appearance-based tracker did not help.
- Open datasets from the notes: the Mendeley PPE set (CC BY 4.0, 175 MB) downloaded too slowly to use; Roboflow and Kaggle sets need accounts; SH17 is non-commercial. The open **construction-safety** set (Roboflow 100, via Hugging Face) turned out to be a **100% near-duplicate** of photos we already had (997 of 997 training, 119 of 119 validation and 90 of 90 test photos), so it added no new training photos and could not serve as an independent test. Its "no vest" labels were used to measure vests (section 2).
- Night-style training followed the notes' advice (darkened copies of our training photos). Held-out validation and test photos were never changed.

## 7. Not measured, or not possible

- The live camera on a real camera, and the spoken alerts by ear.
- Gloves, boots and goggles (second model, accuracy unknown).
- Hi-vis shirts and life jackets: shown in the test cases for inspection, but no labelled photos exist to train or score them.
- A heart attack as such, something falling on a worker, or a worker's cause of falling.
- A real accuracy figure of 99.99%: not claimed.
