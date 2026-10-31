"""Replace slides 9 to 13 of build_deck.py with the text in new_slides.txt (kept for reference), then rebuild the deck."""
from pathlib import Path

here = Path(__file__).parent
script = (here / "build_deck.py").read_text(encoding="utf-8-sig")
new = (here / "new_slides.txt").read_text(encoding="utf-8")
a = script.index("# ---------------------------------------------------------------- 9. results")
b = script.index("# ---------------------------------------------------------------- 14. thanks")
(here / "build_deck.py").write_text(script[:a] + new + script[b:], encoding="utf-8")
print("slides 9-13 replaced")
