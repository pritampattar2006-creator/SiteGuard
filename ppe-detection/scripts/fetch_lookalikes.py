"""Download a few openly licensed photos of hi-vis clothing and life jackets from Wikimedia Commons, to test look-alike objects.

Every photo keeps its author and licence in CREDITS.csv next to it (CC BY and CC BY-SA need that credit; do not remove it).
  python scripts/fetch_lookalikes.py "<output folder>"
"""
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
CATEGORIES = [("High-visibility_clothing", 7), ("Life_jackets", 7)]
OK_LICENCE = re.compile(r"^(CC0|CC BY|CC BY-SA|Public domain|PD)", re.I)
HEADERS = {"User-Agent": "SiteGuard-hackathon-test-cases/1.0 (educational; contact: team HF27-0030)"}


def fetch(request, timeout: int = 60) -> bytes:
    """Open a URL politely: wait and retry when the site says "too many requests"."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as problem:
            if problem.code != 429 or attempt == 5:
                raise
            time.sleep(8 * (attempt + 1))
    raise RuntimeError("unreachable")


def get(params: dict) -> dict:
    time.sleep(1.5)
    return json.loads(fetch(urllib.request.Request(API + "?" + urllib.parse.urlencode({**params, "format": "json"}), headers=HEADERS)))


def main(out: Path) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # photo titles can contain any language
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for category, want in CATEGORIES:
        listed = get({"action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}", "cmtype": "file", "cmlimit": 40})
        titles = [m["title"] for m in listed["query"]["categorymembers"] if m["title"].lower().endswith((".jpg", ".jpeg"))]
        got = 0
        info = get({"action": "query", "titles": "|".join(titles[:30]), "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 900})  # all the metadata in one request
        for page in info["query"]["pages"].values():
            if got >= want:
                break
            title = page["title"]
            ii = (page.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            licence = meta.get("LicenseShortName", {}).get("value", "")
            if not ii.get("thumburl") or not OK_LICENCE.match(licence):
                continue
            author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown")).strip()[:80]
            name = f"{'hivis' if category.startswith('High') else 'lifejacket'}_{got + 1:02d}.jpg"
            try:
                time.sleep(2)
                (out / name).write_bytes(fetch(urllib.request.Request(ii["thumburl"], headers=HEADERS), timeout=120))
            except Exception as problem:  # a slow or missing file must not stop the rest
                print("skipped", title, problem)
                continue
            rows.append({"file": name, "title": title.replace("File:", ""), "author": author, "licence": licence, "page": ii.get("descriptionurl", "")})
            got += 1
            print("got", name, "|", licence, "|", title[:60])
    with open(out / "CREDITS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "title", "author", "licence", "page"])
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "photos with credits written")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
