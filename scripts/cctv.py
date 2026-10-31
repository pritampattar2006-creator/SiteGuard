"""Watch a camera, video file or RTSP stream the way a CCTV desk would.

Every person is tracked, checked for PPE, and named when their face matches an enrolled employee.
A worker who stays without a required item is sent to the supervisor's review queue (once, with a picture and the
face-match suggestion). Names come only from a steady face match and are suggestions: the supervisor confirms the person.

  python scripts/cctv.py --source 0                          # first webcam
  python scripts/cctv.py --source clip.mp4 --location "Gate 2" --push
  python scripts/cctv.py --source rtsp://user:pass@192.168.1.20/stream --push --headless

Keys in the window: q to quit.
"""
import argparse
import base64
import os
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ppe.annotate import draw  # noqa: E402
from ppe.cctv import push_items  # noqa: E402
from ppe.config import Config  # noqa: E402
from ppe.crosscheck import second_opinion  # noqa: E402
from ppe.detector import Detector  # noqa: E402
from ppe.faces import FaceGallery, OpenCVFaces  # noqa: E402
from ppe.identify import FrameNamer  # noqa: E402
from ppe.people import PersonRegistry  # noqa: E402
from ppe.pipeline import analyze  # noqa: E402
from ppe.track import PersistenceFilter, TrackingView  # noqa: E402
from ppe.types import ITEMS  # noqa: E402


def open_source(text: str):
    if text.isdigit():
        return cv2.VideoCapture(int(text), cv2.CAP_DSHOW)
    return cv2.VideoCapture(text)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", default="0", help="camera number, video file or stream URL")
    p.add_argument("--location", default="", help="where this camera is (shown to the supervisor)")
    p.add_argument("--require", default="helmet,vest")
    p.add_argument("--weights", default=str(ROOT / "weights" / "best.pt"))
    p.add_argument("--device", default=None, help="e.g. cpu, or 0 for the first GPU")
    p.add_argument("--every", type=int, default=2, help="check every Nth frame")
    p.add_argument("--face-every", type=int, default=3, help="try faces on every Nth checked frame")
    p.add_argument("--push", action="store_true", help="send confirmed violations to the supervisor's review queue")
    p.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:4000"))
    p.add_argument("--headless", action="store_true", help="no window")
    p.add_argument("--max-seconds", type=float, default=0, help="stop after this long (0 = keep going)")
    p.add_argument("--save", help="write the annotated video here")
    p.add_argument("--no-dummy-names", action="store_true", help="name only enrolled employees (no made-up demo names)")
    args = p.parse_args()

    config = replace(Config(), required=tuple(i for i in args.require.split(",") if i in ITEMS))
    detector = Detector(args.weights, device=args.device)
    view = TrackingView(detector)
    gallery = FaceGallery(ROOT / "data" / "faces" / "gallery.json")
    face_dir = ROOT / "weights" / "faces"
    faces = OpenCVFaces(face_dir / "face_detection_yunet_2023mar.onnx", face_dir / "face_recognition_sface_2021dec.onnx")
    registry = PersonRegistry(ROOT / "data" / "faces" / "people.json")
    namer = FrameNamer(faces, gallery, registry, str(args.source)[:60], args.location, face_every=args.face_every, dummy_names=not args.no_dummy_names)
    print(f"Faces enrolled: {gallery.count()}; dummy demo names {'off' if args.no_dummy_names else 'on (made-up names, same face = same name)'}")
    announced: set = set()

    capture = open_source(args.source)
    if not capture.isOpened():
        sys.exit(f"Cannot open the source: {args.source}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    writer = None
    persistence = PersistenceFilter(config.persist_window, config.persist_min)
    ingest_key = os.environ.get("INGEST_KEY", "dev-ingest-key")
    started, frame_no, checked, sent = time.time(), -1, 0, 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_no += 1
            if frame_no % args.every:
                continue
            checked += 1
            result = analyze(frame, config, view)
            second_opinion(frame, result, detector, config)  # a second model may hold back a helmet call
            annotated = draw(frame, result, show_unassigned=False)

            seen_now = namer.update(frame, result, annotated, checked)
            for who in seen_now.values():
                if who.employee_id not in announced:
                    announced.add(who.employee_id)
                    print(f"[{datetime.now():%H:%M:%S}] {who.name} ({who.employee_id}{', dummy' if who.dummy else ''}) in view")

            items = []
            for verdict in result.verdicts:
                for item in config.required:
                    state = verdict.helmet_state if item == "helmet" else verdict.vest_state
                    if persistence.update(verdict.worker_id, item, state):
                        who = seen_now.get(verdict.worker_id)
                        print(f"[{datetime.now():%H:%M:%S}] worker {verdict.worker_id}: no {item}" + (f"  (looks like {who.name})" if who else ""))
                        ok_jpg, jpg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 88])
                        items.append({
                            "workerRef": f"Worker {verdict.worker_id}", "missing": f"NO {item.upper()}", "reason": verdict.reason,
                            "location": args.location, "source": "cctv", "sourceName": str(args.source)[:120],
                            "occurredAt": datetime.now(timezone.utc).isoformat(),
                            "evidenceBase64": base64.b64encode(jpg.tobytes()).decode(),
                            "suggested": ({"employeeId": who.employee_id, "name": who.name, "jobRole": who.job_role,
                                           "department": who.department, "score": who.score, "dummy": who.dummy} if who else None),
                        })
            if items and args.push:
                try:
                    sent += push_items(args.api, ingest_key, items)
                except OSError as problem:  # the API being down must not stop the camera
                    print("Could not reach the API:", problem)

            if args.save:
                if writer is None:
                    h, w = annotated.shape[:2]
                    writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps / args.every, (w, h))
                writer.write(annotated)
            if not args.headless:
                cv2.imshow("SiteGuard CCTV (q to quit)", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if args.max_seconds and time.time() - started > args.max_seconds:
                break
    finally:
        capture.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
    print(f"Done. {checked} frames checked, {sent} cases sent to the review queue.")


if __name__ == "__main__":
    main()
