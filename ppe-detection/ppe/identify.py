"""Names for the people in a picture or clip: enrolled employees first, then steady dummy identities, one face at a time."""
from __future__ import annotations

from .annotate import draw_name
from .appearance import DressBook, signature
from .cctv import IdentityTracker
from .faces import FaceGallery, OpenCVFaces, Identity, face_for_person
from .people import PersonRegistry


class FrameNamer:
    """Works out who each tracked person is. Feed it every checked frame; it looks at faces every `face_every`th one.

    For video, a name is shown only once the same person has matched in several frames (IdentityTracker), and tracks that turn
    out to be the same face share one identity, so a person whose track number changed is still the same person.
    """

    def __init__(self, faces: OpenCVFaces | None, gallery: FaceGallery, registry: PersonRegistry | None, source: str, location: str = "",
                 face_every: int = 3, min_votes: int = 2, dummy_names: bool = True, dress: DressBook | None = None, footage_key: str = ""):
        self.faces, self.gallery, self.registry = faces, gallery, registry
        self.source, self.location, self.face_every = source, location, face_every
        self.dummy_names = dummy_names and registry is not None
        self.tracker = IdentityTracker(min_votes=min_votes)
        self.latest: dict[int, Identity] = {}  # worker id -> who they are now
        self.ever: dict[int, Identity] = {}  # worker id -> who they were last known to be (for incidents)
        self.dress = dress
        self.footage_key = footage_key  # identifies this exact footage, so the same upload always gives the same made-up names
        self.first_seen: dict[int, tuple] = {}  # worker id -> (checked frame, x cell, y cell) where the person first appeared
        self.sigs: dict[int, list] = {}  # worker id -> this person's dress signatures so far

    def _resolve(self, image, face) -> Identity | None:
        embedding = self.faces.embed(image, face)
        who = self.gallery.identify(embedding)
        if who is None and self.dummy_names:
            good = face.score >= 0.85 and (face.box[2] - face.box[0]) >= 48  # only a clear, reasonably large face may start a new identity
            who = self.registry.resolve(embedding, can_register=good)
        return who

    def update(self, image, result, annotated, checked: int) -> dict[int, Identity]:
        if self.faces is None or (not self.gallery.count() and not self.dummy_names):
            return {}
        for match in result.matches:
            if match.worker_id not in self.first_seen:
                cx, cy = (match.person.box[0] + match.person.box[2]) // 2, (match.person.box[1] + match.person.box[3]) // 2
                self.first_seen[match.worker_id] = (checked, cx // 60, cy // 60)
        if self.dress is not None and image is not None:  # remember what each tracked person is wearing
            for match in result.matches:
                sig = signature(image, match.person.box)
                if sig is not None and len(self.sigs.setdefault(match.worker_id, [])) < 6:
                    self.sigs[match.worker_id].append(sig)
        if checked % self.face_every == 0:
            self.gallery.reload_if_changed()
            found = self.faces.detect(image)
            for match in result.matches:
                face = face_for_person(found, match.person.box)
                if face:
                    self.tracker.update(match.worker_id, self._resolve(image, face))
        self.latest = {}
        for match in result.matches:
            who = self.tracker.who(match.worker_id)
            if who:
                self.latest[match.worker_id] = self.ever[match.worker_id] = who
                if self.dress is not None:  # a face is known: learn today's clothes for this person
                    for sig in self.sigs.get(match.worker_id, []):
                        self.dress.add(who.employee_id, sig)
                if annotated is not None:
                    draw_name(annotated, match.person.box, f"{who.name} - {who.job_role}" if who.job_role else who.name)
                if self.registry is not None:
                    self.registry.see(who, self.source, self.location)
        return self.latest

    def settle(self, worker_id: int) -> Identity | None:
        """Who a tracked person is, once the footage is done. Call it for people who broke a rule.

        1. A face (now or earlier) decides first.
        2. Otherwise their clothes are compared with everyone seen today: they are named only if the clothes clearly match exactly one
           known person, or clearly match nobody (then a new made-up identity is made for them). Look-alikes are never merged.
        3. If that gives nothing (too small, cut off, dressed like several people), they still get a made-up name tied to this exact
           footage: the same footage always gives the same name, but it does not mean the system knows who they are.
        """
        known = self.ever.get(worker_id)
        if known is not None or not self.dummy_names or self.registry is None:
            return known
        who = self._by_dress(worker_id)
        if who is None and self.footage_key and worker_id in self.first_seen:
            frame, cx, cy = self.first_seen[worker_id]
            who = self.registry.identity_for_key(f"{self.footage_key}|{frame}|{cx}|{cy}")
        if who is None:
            return None
        self.ever[worker_id] = who
        self.registry.see(who, self.source, self.location)
        return who

    def _by_dress(self, worker_id: int) -> Identity | None:
        if self.dress is None:
            return None
        verdicts = [self.dress.match(sig) for sig in self.sigs.get(worker_id, [])]
        if not verdicts:
            return None
        matches = {who for who, state in verdicts if state == "match"}
        if any(state == "ambiguous" for _, state in verdicts) or len(matches) > 1:
            return None
        if matches:
            key = matches.pop()
            person = next((p for p in self.registry.people() if p["employeeId"] == key), None)
            return Identity(key, person["name"], person["jobRole"], person["department"], 1.0, True) if person else None
        if all(state == "unknown" for _, state in verdicts):
            who = self.registry.new_unseen()
            if who is not None:
                for sig in self.sigs[worker_id]:
                    self.dress.add(who.employee_id, sig)
            return who
        return None
