"""Enrol many workers' faces at once from a folder of photos.

Layout:
  faces_in/
    roster.csv                 employeeId,name,jobRole,department
    E001/  photo1.jpg photo2.jpg
    E002/  photo1.jpg

  python scripts/enroll_folder.py faces_in --consent-confirmed

Run it only for employees who have been told how their face template is used and have agreed (India's DPDP Act
expects notice and consent). Only a numeric template is stored; the photos are not copied anywhere.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ppe.faces import FaceGallery, OpenCVFaces  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder")
    p.add_argument("--consent-confirmed", action="store_true", help="I confirm every person in this folder has agreed")
    args = p.parse_args()
    if not args.consent_confirmed:
        sys.exit("Refusing to enrol faces without --consent-confirmed (every person must have agreed first).")

    folder = Path(args.folder)
    face_dir = ROOT / "weights" / "faces"
    faces = OpenCVFaces(face_dir / "face_detection_yunet_2023mar.onnx", face_dir / "face_recognition_sface_2021dec.onnx")
    gallery = FaceGallery(ROOT / "data" / "faces" / "gallery.json")
    with open(folder / "roster.csv", newline="", encoding="utf-8") as f:
        roster = list(csv.DictReader(f))

    for person in roster:
        eid = person["employeeId"].strip().upper()
        photos = [x for x in (folder / eid).glob("*") if x.suffix.lower() in {".jpg", ".jpeg", ".png"}] if (folder / eid).is_dir() else []
        used = 0
        for photo in photos:
            image = cv2.imread(str(photo))
            found = [x for x in faces.detect(image) if x.score >= 0.8] if image is not None else []
            if len(found) != 1:
                print(f"  {eid} {photo.name}: skipped (needs exactly one clear face, found {len(found)})")
                continue
            gallery.enroll(eid, person["name"], person.get("jobRole", ""), person.get("department", ""), faces.embed(image, found[0]), True)
            used += 1
        print(f"{eid} {person['name']}: {used} photo(s) enrolled")
    print(f"Faces enrolled in total: {gallery.count()}")


if __name__ == "__main__":
    main()
