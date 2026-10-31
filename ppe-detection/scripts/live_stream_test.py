"""Live-camera check without a camera: serves eval/cases/case_10.jpg as a local HTTP video stream and points the running detector service at it.

  python scripts/live_stream_test.py        (run from the project folder, with `python detector_service.py` running)
It does not send anything to the supervisor (push is off).
"""
import json, threading, time, urllib.request, cv2, numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
img = cv2.imread(r"eval/cases/case_10.jpg")
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame"); self.end_headers()
        i = 0
        try:
            while True:
                f = img.copy(); cv2.putText(f, str(i), (5, 20), 0, 0.5, (255, 255, 255), 1); i += 1
                ok, b = cv2.imencode(".jpg", f)
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(b) + b.tobytes() + b"\r\n"); time.sleep(0.1)
        except Exception: pass
srv = ThreadingHTTPServer(("127.0.0.1", 8090), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def call(path, body=None):
    req = urllib.request.Request("http://localhost:5000" + path, data=json.dumps(body).encode() if body is not None else None, headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
r = call("/live", {"url": "http://127.0.0.1:8090/video", "required": ["helmet", "vest"], "location": "test", "sector": "", "push": False}); print("started", r)
fid = r["id"]
for _ in range(12):
    time.sleep(2)
    try: s = call(f"/live/{fid}"); 
    except Exception as e: print("status err", e); continue
    print({k: s.get(k) for k in ("status", "error", "analysed", "frames")}, "workers:", len(s.get("workers", [])))
    if s.get("analysed", 0) >= 3: break
jpg = urllib.request.urlopen(f"http://localhost:5000/live/{fid}/frame.jpg", timeout=10).read() if False else None
print("stop", call(f"/live/{fid}/stop", {}))
