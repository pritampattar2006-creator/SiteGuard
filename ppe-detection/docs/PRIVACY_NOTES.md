# Privacy notes

Not legal advice. The Digital Personal Data Protection Act, 2023 (India) applies to digital personal data; have your institution's legal or compliance
contact confirm how it applies to your site before any real deployment.

## What personal data SiteGuard handles
- **Photos and video of workers.** A person's image is personal data.
- **Names and employee IDs** in the register, if a supervisor adds them.
- **Violation records** tied to a named worker: time, place, evidence photo, status, a time log.

## What it does not do
- It does **not** recognise faces or identify anyone. "Worker 3" in a photo is just a number for that image. A name is attached only when a supervisor assigns it by hand.
- It does not send data anywhere. Everything runs and is stored on the machine where it is installed (`data/violations.db`, `outputs/`).

## Practices this project follows or should follow before real use
| Practice | Status |
|---|---|
| Tell workers what is recorded and why (notice), and obtain consent or rely on a lawful ground for employment-related processing | **Not built.** The institution must do this |
| Collect only what is needed: evidence is a photo and a close-up of the worker involved; no face recognition | Followed |
| Keep data only as long as needed (a retention period), and delete on request | **Not built.** There is no automatic deletion yet |
| Protect the data: access control, hashed passwords, encrypted storage | **Not built.** The demo app has no login. Do not expose it to a network |
| Let a worker see and dispute their own cases | Partly built (register with a time log and status); no worker login yet |
| Keep an audit log of who changed what | Partly built: every case has an event log. No separate audit log for escalations |
| Human review before any formal notice or action | Required by design: the system proposes, a supervisor decides |

## Automated decisions
A detection is a suggestion. A worker we cannot judge fairly is sent to NEEDS REVIEW rather than accused, and no violation should be acted on without a supervisor
looking at the evidence photo. The worker-down alert only means "someone should check"; it cannot say why a person is on the ground.

## Before deploying
1. Decide who is responsible for the data and who workers can ask about it.
2. Add notice and consent or another lawful basis, a retention period, and a way to delete a worker's records.
3. Add logins and role-based access, hashed passwords, and encrypted storage.
4. Confirm the required equipment per role with the safety officer (`config/ppe_rules.json`).

## Face matching (optional)

- Purpose: to suggest which enrolled employee a flagged worker may be. The supervisor always confirms the person before anything is recorded; a match alone creates no violation and no penalty.
- Consent: an employee is enrolled only after being told how the template is used and agreeing (the enrolment page and `scripts/enroll_folder.py` both refuse to run without a consent confirmation). Under India's DPDP Act 2023 this needs a clear notice and a stated purpose; ask the site's legal/HR owner to approve the wording.
- What is stored: a numeric face template per photo (at most 5 per person) in `data/faces/gallery.json`. Photos are not kept. Removing a person (supervisor, Team page) deletes their templates.
- The CCTV script writes `outputs/cctv/sightings.csv` (time, who, where). Decide how long to keep it and who may read it; the system does not delete it for you.
- Accuracy has not been measured on real site footage. Helmets, distance, angle and poor light all reduce it. Models: OpenCV YuNet (detector) and SFace (recogniser).

## Demo identities (made-up names)

- When "demo names" is on (the default on the demo desk), a clear face that is not an enrolled employee is given a made-up name, role and ID (E001, E002, ...) from `config/dummy_roster.json`, and the same face gets the same one next time. The names belong to nobody.
- To recognise the same face again, a numeric face template is kept in `data/faces/people.json` (never the photo). Templates expire after 7 days without a sighting, and a supervisor can clear them all (Face matching page).
- This is for demos and testing. For real use, turn demo names off so that only employees who have agreed and been enrolled are named, and decide who may see the sightings log.
- Measured on 160 clips of 4 people (home videos, so only a rough guide): no two different people were ever merged, and each real person ended up with 1 or 2 names. Faces smaller than about 48 pixels (typical in wide shots of a crowd) are not used to start a new identity, so those workers stay unnamed.

## Made-up names for people whose face is not clear

- A person who broke a rule but whose face is not clear gets a made-up name, tied to that exact footage (a fingerprint of the video file or picture and where the person first appeared). The same footage always gives the same names. Nothing about a real person is stored for this.
- Clothes are compared only for the same day and only under a very strict rule; look-alikes are never merged. The clothing signatures are colour counts, not pictures, and are cleared at the end of the day.
- For real use, switch the made-up names off (`DUMMY_NAMES=0` for the detector service, and `DEMO_MODE=0` for the API), so that only enrolled employees who agreed are named.
