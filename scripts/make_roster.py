"""Write config/dummy_roster.json: made-up employees (name, role, department, monthly salary) that match the demo identities
the detector gives to unknown faces (E001, E002, ...). Everything in it is invented. Copy the file to the web API's config folder."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ppe.people import dummy_profile  # noqa: E402

BASE = {"Mason": 24000, "Electrician": 32000, "Carpenter": 27000, "Welder": 30000, "Scaffolder": 26000, "Helper": 18000,
        "Painter": 22000, "Plumber": 28000, "Crane operator": 40000, "Bar bender": 25000}

roster = []
for n in range(1, 121):
    p = dummy_profile(n)
    roster.append({**p, "monthlySalary": BASE.get(p["jobRole"], 22000) + (n % 5) * 500})
(ROOT / "config" / "dummy_roster.json").write_text(json.dumps({"_read_me": "Invented people for demos. Not real.", "employees": roster}, indent=2), encoding="utf-8")
print(len(roster), "dummy employees written")
