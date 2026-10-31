# SiteGuard web

Three sites and two services, all running on this computer:

| What | Address | For |
|---|---|---|
| Supervisor panel | http://localhost:3002 | every employee (photo, role, salary, violations, sightings), the review queue, penalties, remarks |
| Employee portal | http://localhost:3001 | one employee's personal feed, alerts, violations, salary, penalties |
| Demo desk | http://localhost:3003 | upload a photo or video, or open a live camera; spoken alerts; no sign-in |
| API | http://localhost:4000 | Node + Express, embedded MongoDB-style store (NeDB) |
| Detector service | http://localhost:5000 | Python, the PPE, face and object-check models (`ppe-detection` folder) |

## Sign in

The supervisor panel and the employee portal use normal sign-in. The accounts are dummy: **the supervisors that exist now (`S001`, `S002`, `S003`) and every employee use the same password, `123456789`**. Supervisors created later choose their own.

- Head supervisor (sees every sector, sets up sectors and supervisors): `S001` / `123456789`
- Sector supervisors: `S002` (Wireman) / `123456789`, `S003` (Lineman) / `123456789`. They see only their own sector's cases.
- Employees: `E001` to `E120`, all with the password `123456789` (so `E001` / `123456789`). Employees a supervisor adds get an ID like `BCE101` and the same password. Change it before any real use.

For a quick demo without typing, set `VITE_AUTO_LOGIN=1` and each site signs itself in. Change all of this before anything goes on the internet.

## Sectors, supervisors and the conditions class

A **sector** is a kind of work (Construction, Wireman, Lineman, or any the head supervisor adds). Each sector has its own **conditions class** (a label) and its own list of **gear that must be worn**. In the supervisor panel, under *Sectors and supervisors*, the head supervisor can:

- add or edit a sector and choose which gear is required;
- create a supervisor account for a sector (the code is made for you and the password is the code plus @123 unless one is typed).

A supervisor sees and decides only on the cases of their own sector. The starting gear lists are examples; the site's safety officer confirms the real ones.

## The demo desk is automatic

The desk has one sector menu and one common upload button (a photo or a video), plus a live camera. The sector sets the required gear and the place, and everything caught is sent on by itself. There are no settings to fill in.

## Run everything

```
npm install          # once
npm run start:all    # API, the three sites and the detector service together
node api/src/seed.js --demo   # optional: a believable history for demos
npm run smoke        # checks every service and walks one case through the whole flow
npm test             # API, alert-logic and screen-rendering tests
```

Settings are in `.env.example`; nothing needs to be set for local demos.

## How a catch flows (no human step until the supervisor decides)

1. A photo, video or live camera frame goes to the detector on the demo desk. Every worker is checked for the required gear, and the "no helmet" calls are cross-checked by a second model first.
2. Anyone who broke a rule gets a name: an enrolled employee if their face is known, otherwise a made-up name that stays the same for the same footage. Only those people are spoken to, at most once every 10 minutes ("Raju, please wear your helmet"). There is no announcement to everyone.
3. Each person who broke a rule is sent to the supervisor automatically, with the picture and a short remark written from the facts of the case (who, what, where, when, how many times, earlier violations). The supervisor can edit the remark.
4. The employee sees it in their personal feed straight away: the date, the time, the place and how it was caught. It becomes a violation only when a supervisor confirms it.
5. At most one violation per person per day. Caught again the same day: the catch count goes up. The next day: a new violation. Three confirmed violations in 30 days propose a penalty, which a supervisor must approve and the employee can dispute.

Salaries, names and penalty amounts are made up. What was measured and what was not is in `ppe-detection/docs/ACCURACY_MEASURED.md`.
