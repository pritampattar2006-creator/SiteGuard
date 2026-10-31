# 3-minute demo script

Open the app (`streamlit run app.py`). Keep the images ready in one folder.

| Time | Show | Say |
|---|---|---|
| 0:00 | Title page | "Supervisors cannot watch every worker. This checks each worker for a helmet and a vest and flags who is missing what." |
| 0:20 | **Easy photo**, one compliant worker | "One worker, green box, helmet and vest matched to this worker." |
| 0:45 | **Busy site photo** (several workers) | "Every worker gets their own verdict. The equipment is matched to the person wearing it, not just detected somewhere in the image." |
| 1:15 | **Helmet in hand / on a table** (your test photo) | "The helmet is in nobody's head zone, so it is shown as unassigned and the worker is flagged. A helmet anywhere in the image does not clear everyone." |
| 1:40 | **Photo with no PPE** (the brick-site photo) | "Red boxes, NO HELMET + NO VEST for each worker." |
| 2:00 | **Crowded or distant photo** | "Where it cannot judge fairly, it says REVIEW in amber instead of accusing someone." Open "How the decisions were made" to show the reason sentences |
| 2:15 | **Dark photo** | "Low-light enhancement is applied automatically." |
| 2:30 | **One honest failure** (for example the look-alike clothing case) | "This is where it still goes wrong, and this is what we would improve next." |
| 2:45 | Download the CSV, show the evaluation table | "Everything exports, and here is our accuracy by case, including the failures." |
| 3:00 | Optional: Video page | "For clips, each worker is tracked and a violation is reported once, with an evidence frame." |

## Extra beats (if time allows)

| Show | Say |
|---|---|
| Sidebar **Worker role**: switch from General worker to Welder | "What each role must wear comes from a config file the safety officer owns, not from our code" |
| **Register** tab: save violations from a photo, assign a name, open the case, download the PDF notice | "Every case has evidence, a named worker and a time log. We never recognise faces: a supervisor attaches the name" |
| **Video** tab: a clip with a worker falling and staying down (if you have one) | "A person who falls and does not get up raises a worker-down alert. It cannot tell why, so it says: check now" |
| **Rules** tab | "These are starter values to be confirmed by the safety officer. We did not invent safety standards" |

Tip: rehearse once with the exact photos you will use, so you know which ones behave well and which one is your honest failure.
