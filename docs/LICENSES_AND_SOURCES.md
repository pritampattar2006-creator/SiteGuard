# Open-source licences and sources

Everything below is open source. We keep every licence and credit; nothing is stripped or hidden. Code in `ppe/`, `scripts/`, `app.py`
and `tests/` was written for this project. Other open-source projects were read for ideas only (concepts such as tracking each worker
across frames, confirming a violation only when it persists, and writing an incident log); no code was copied from them.

## Which models are open source

| Model | Licence | Open source? | Notes |
|---|---|---|---|
| **Ultralytics YOLO11** (what we use) | AGPL-3.0 | Yes (copyleft) | If you distribute software that uses it, or offer it over a network, you must publish your source under AGPL-3.0. Fine for a hackathon or an open project; a company that wants to keep its code private needs an Ultralytics enterprise licence |
| **RF-DETR** (Nano to Large) | Apache-2.0 | Yes (permissive) | Can be used in closed products. Larger sizes (XL, 2XL) are under a separate Roboflow licence. Would need a new wrapper in `ppe/detector.py` |
| **D-FINE** | Apache-2.0 | Yes (permissive) | Same: needs integration work |
| Community PPE weights found on Hugging Face and GitHub | Not stated | Unclear | Not used: no licence, different classes |

## What this project uses

| Component | Licence | Role |
|---|---|---|
| Ultralytics YOLO11 + ByteTrack | AGPL-3.0 | Detection model and worker tracking |
| PyTorch, torchvision | BSD-style | Deep-learning engine |
| OpenCV | Apache-2.0 | Images, video, drawing |
| Streamlit | Apache-2.0 | Web app |
| pandas, NumPy | BSD-3 | Tables, arrays |
| ReportLab | BSD | PDF notices and reports |
| SQLite (Python standard library) | Public domain | Violation register |
| lap | BSD | Assignment solver for the tracker |
| pytest | MIT | Tests |

## Datasets

| Dataset | Licence | Use |
|---|---|---|
| Construction-PPE (Ultralytics) | AGPL-3.0 | Training: person, helmet, vest, head (no_helmet), plus gloves, boots, goggles for the second model |
| CHVG (Md. Ferdous and Sk. Md. Masudul Ahsan, 2022, PeerJ Computer Science 8:e999) | CC BY 4.0 | Training: person, helmet, vest, head |
| Photos supplied by the team | Team's own | Testing and checking only, never training |

Weights trained on these datasets inherit their terms.

## About reusing other projects

If an open-source repository is ever reused as code (not just as an idea), its licence must be followed: keep its copyright and licence notices,
state what was taken, and respect its terms (MIT and Apache-2.0 allow reuse with notices; GPL and AGPL require the combined work to carry the same licence;
code with no licence cannot be copied). We do not remove attribution, and we recommend nobody does: it is a condition of the licences, and it protects you.

## Added for the fall detector

| Component | Licence | Use |
|---|---|---|
| GMDCSA24 fall dataset (Alam et al., 2024) | MIT | Training the experimental learned fall detector (acted indoor falls, 4 people) |
| scikit-learn | BSD-3 | Training the fall classifier |
| YOLO11n-pose (Ultralytics) | AGPL-3.0 | Body-joint detection for the learned fall detector |


## Added for the test cases and night training

| Component | Licence | Use |
|---|---|---|
| Wikimedia Commons photos of hi-vis clothing and life jackets | CC BY, CC BY-SA or public domain, per photo | Test photos for vest look-alikes. Author and licence of each are in `test_cases/05_hi_vis_and_life_jacket_lookalikes/input/CREDITS.csv` and must stay with the photos |
| "Dataset of Personal Protective Equipment (PPE)" (Huang et al., National Chin-Yi University of Technology, Mendeley Data, DOI 10.17632/zkzghjvpn2.6) | CC BY 4.0 | Considered (2,286 helmet and vest photos) but **not used**: the download was too slow to finish. If used later, credit it |
| Night-style training copies | made by us | Darkened copies (brightness, gamma, noise) of our own training photos, as the dataset notes recommend when real night data is unavailable |

Datasets that need an account (Roboflow Universe, Kaggle) or are non-commercial (SH17, CC BY-NC-SA) were not used.
