import { useEffect, useRef, useState } from 'react';
import { canSpeak, newAlertState, planAlerts, sceneSummary, speak } from './alerts.js';
import { API_BASE, session } from './api.js';
import { Avatar, Chip, Err, PageHead } from './ui.jsx';

// The detection desk (the demo site): upload a photo or a video, or open a live camera. Everything caught is spoken aloud, shown
// in the alert log, and (if switched on) sent to the supervisor and to the employee's own site. Nothing becomes a violation
// until a supervisor confirms it. The detector runs as its own service.
export const DETECTOR = import.meta.env.VITE_DETECTOR_URL || `http://${window.location.hostname}:5000`;

async function call(path, options = {}) {
  const res = await fetch(DETECTOR + path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Detector error (${res.status})`);
  return data;
}
const postJson = (path, body) => call(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
const readFile = (file) => new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = reject; r.readAsDataURL(file); });
// A short siren (two alternating tones) for an accident alert. Browsers only allow sound after the person has clicked on the page once.
function sirenFor(ms = 4000) {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    const ac = new AC(); const osc = ac.createOscillator(); const gain = ac.createGain();
    osc.type = 'square'; gain.gain.value = 0.08; osc.connect(gain); gain.connect(ac.destination); osc.start();
    let high = false; osc.frequency.value = 620;
    const t = setInterval(() => { high = !high; osc.frequency.setValueAtTime(high ? 900 : 620, ac.currentTime); }, 420);
    setTimeout(() => { clearInterval(t); try { osc.stop(); ac.close(); } catch { /* done */ } }, ms);
  } catch { /* no sound available */ }
}
const clock = (t = Date.now()) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

function useDetectorStatus() {
  const [up, setUp] = useState(null);
  useEffect(() => {
    let alive = true;
    const ping = () => fetch(`${DETECTOR}/health`).then((r) => alive && setUp(r.ok)).catch(() => alive && setUp(false));
    ping();
    const t = setInterval(ping, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return up;
}

const verdictTone = { COMPLIANT: 'ok', VIOLATION: 'bad', NEEDS_REVIEW: 'warn' };

export function WorkersTable({ workers }) {
  return (
    <div className="scroll"><table>
      <thead><tr><th>Employee</th><th>Verdict</th><th>Missing</th></tr></thead>
      <tbody>{workers.length ? workers.map((w) => (
        <tr key={w.id}>
          <td><div className="who-cell"><Avatar name={w.identity ? w.identity.name : '?'} size={30} /><div><b>{w.label}</b><small>{w.identity ? `${w.identity.employeeId} · ${w.identity.jobRole || ''}${w.identity.via === 'dress' ? ' · matched by dress' : ''}` : 'not identified'}</small></div></div></td>
          <td><Chip tone={verdictTone[w.status]}>{w.status.replace('_', ' ')}</Chip>{w.crosscheck === 'disagree' && <div className="small muted">second model disagrees</div>}</td><td>{w.missing.join(', ') || '—'}</td></tr>
      )) : <tr><td colSpan="3">No workers found in this picture.</td></tr>}</tbody>
    </table></div>
  );
}

export function Scene({ workers }) {
  const s = sceneSummary(workers);
  if (!s.total) return null;
  return (
    <div className="scene">
      <div className="scene-big"><b>{s.ok}</b> of {s.total} fully equipped</div>
      <div className="scene-chips">
        {s.helmetsMissing > 0 && <Chip tone="bad">{s.helmetsMissing} without a helmet</Chip>}
        {s.vestsMissing > 0 && <Chip tone="bad">{s.vestsMissing} without a vest</Chip>}
        {s.review > 0 && <Chip tone="warn">{s.review} need a closer look</Chip>}
        {!s.caught && !s.review && <Chip tone="ok">everyone is equipped</Chip>}
      </div>
      {s.notWearing.length > 0 && <p className="small" style={{ margin: '.5rem 0 0' }}><b>Not wearing gear right now:</b> {s.notWearing.map((n) => `${n.label} (${n.items.join(' + ')})`).join(', ')}</p>}
    </div>
  );
}

// sectorLock: a supervisor's own sector (the desk is then fixed to it); extraRight: more panels under the live alerts.
export function DetectDesk({ title = 'Detection desk', sectorLock = '', extraRight = null }) {
  const up = useDetectorStatus();
  const [sectors, setSectors] = useState([]);
  const [sectorId, setSectorId] = useState(() => { try { return localStorage.getItem('siteguard.sector') || ''; } catch { return ''; } });
  const [mode, setMode] = useState('upload');
  const [speed, setSpeed] = useState(() => { try { return localStorage.getItem('siteguard.speed') || 'fast'; } catch { return 'fast'; } });
  const [every, setEvery] = useState('');  // optional: check every N frames (beats the preset)
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);

  const [result, setResult] = useState(null);
  const [sent, setSent] = useState('');
  const [job, setJob] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [camError, setCamError] = useState('');
  const [auto, setAuto] = useState(false);
  const [log, setLog] = useState([]);
  const [banner, setBanner] = useState(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [accident, setAccident] = useState(null);
  const [caughtTotal, setCaughtTotal] = useState(0);
  const video = useRef(null);
  const stream = useRef(null);
  const alertState = useRef(newAlertState());
  const announced = useRef(new Set());
  const live = useRef({});

  // Everything below is automatic: the sector (kind of work) decides which gear is required and where this is. Supervisors set those up in
  // the supervisor panel; the desk only picks the sector. Everyone caught is sent on by itself, and each person is spoken to at most once in 10 minutes.
  const sector = sectors.find((s) => s.id === (sectorLock || sectorId)) || (sectorLock ? null : sectors[0]);
  const required = sector?.requiredItems || ['helmet', 'vest'];
  const location = sector?.location || '';
  const COOLDOWN_MIN = 10;
  live.current = { speed, every, voiceOn, location, required, busy, mode, sectorId: sector?.id || '', sectorName: sector?.name || '' };

  useEffect(() => { fetch(`${API_BASE}/api/sectors/public`).then((r) => r.json()).then((l) => setSectors(Array.isArray(l) ? l : [])).catch(() => {}); }, []);
  useEffect(() => { if (!banner) return undefined; const t = setTimeout(() => setBanner(null), 9000); return () => clearTimeout(t); }, [banner]);
  const pickSector = (id) => { setSectorId(id); try { localStorage.setItem('siteguard.sector', id); } catch { /* not remembered */ } };

  // ---- speaking and logging ------------------------------------------------------------------
  const raise = (workers, where) => {
    const o = live.current;
    const plan = planAlerts(workers, where, alertState.current, Date.now(), { personCooldownMs: COOLDOWN_MIN * 60000 });
    alertState.current = plan.state;
    if (!plan.log.length) return;
    plan.speak.forEach((t) => { if (o.voiceOn) speak(t); });
    const at = Date.now();
    setLog((l) => [...plan.log.map((e, i) => ({ ...e, at, id: `${at}-${i}`, spoken: o.voiceOn })), ...l].slice(0, 60));
    setBanner({ ...plan.log[0], at });
    setCaughtTotal((n) => n + plan.log.reduce((s, e) => s + (e.count || 1), 0));
  };
  const enableVoice = () => { if (!canSpeak()) { setError('This browser cannot speak. Use Chrome or Edge.'); return; } setVoiceOn(true); speak('Voice alerts are on. I will call out anyone without safety gear.'); };
  const disableVoice = () => { setVoiceOn(false); try { window.speechSynthesis?.cancel(); } catch { /* nothing was being spoken */ } };  // stops what is being said, too
  const voiceSwitch = (
    <button type="button" className={`voice-toggle ${voiceOn ? 'on' : ''}`} aria-pressed={voiceOn} onClick={voiceOn ? disableVoice : enableVoice} title={voiceOn ? 'Spoken alerts are on. Click to turn them off.' : 'Click to hear anyone caught without gear called out.'}>
      <span className="dot" aria-hidden="true" />Voice {voiceOn ? 'on' : 'off'}
    </button>
  );

  // ---- one common upload button: a photo or a video -------------------------------------------
  const meta = (extra = {}) => ({ required: live.current.required, location: live.current.location, sector: live.current.sectorId, dummyNames: true, source: live.current.mode === 'camera' ? 'live camera' : 'photo upload', ...extra });
  const check = async (image, sourceName = '') => {
    setBusy(true); setError(''); setSent(''); setJob(null);
    const inputAtStart = live.current.mode;
    try {
      const r = await postJson('/analyze', { image, ...meta({ sourceName }), push: true });
      if (live.current.mode !== inputAtStart) return; // only one input is on: the one this came from was turned off
      setResult(r);
      raise(r.workers, live.current.location);
      if (r.pushed || r.repeats) setSent(`Sent to the supervisor: ${r.pushed} new case(s)${r.repeats ? `, ${r.repeats} already caught today (count raised)` : ''}.`);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const uploadVideo = async (file) => {
    setError(''); setSent(''); setResult(null); announced.current = new Set(); setVideoUrl(URL.createObjectURL(file));
    setJob({ status: 'uploading', name: file.name, done: 0, total: 0, incidents: [] });
    try {
      const { id } = await call(`/video?required=${live.current.required.join(',')}&name=${encodeURIComponent(file.name)}&dummy=1&location=${encodeURIComponent(live.current.location)}&sector=${encodeURIComponent(live.current.sectorId)}&speed=${live.current.speed === 'turbo' ? 'fast' : live.current.speed}${live.current.every ? `&every=${live.current.every}` : live.current.speed === 'turbo' ? '&every=6' : ''}`, { method: 'POST', headers: { 'content-type': file.type || 'video/mp4' }, body: file });
      if (live.current.mode !== 'upload') return; // upload was turned off while the video was being sent
      setJob({ id, status: 'running', name: file.name, done: 0, total: 0, incidents: [] });
    } catch (err) { setError(err.message); setJob(null); }
  };
  const takeFile = async (file) => {
    if (!file) return;
    if (file.type.startsWith('video/')) uploadVideo(file);
    else if (file.type.startsWith('image/')) check(await readFile(file), file.name);
    else setError('Choose a photo or a video file.');
  };
  const upload = (e) => { const file = e.target.files?.[0]; e.target.value = ''; takeFile(file); };
  const [drag, setDrag] = useState(false);

  // ---- a phone (or any IP camera) on the same WiFi: the detector pulls its stream and shows the marked-up picture live -------
  const [phoneUrl, setPhoneUrl] = useState(() => { try { return localStorage.getItem('siteguard.phoneurl') || ''; } catch { return ''; } });
  const [phone, setPhone] = useState(null);
  const checks = useRef(0);
  const phoneRunning = !!phone && ['connecting', 'live'].includes(phone.status);
  const startPhone = async () => {
    setError(''); setPhone(null); checks.current = 0;
    try { localStorage.setItem('siteguard.phoneurl', phoneUrl.trim()); } catch { /* not remembered */ }
    try {
      const { id, url: used } = await postJson('/live', { url: phoneUrl.trim(), required: live.current.required, location: live.current.location, sector: live.current.sectorId });
      if (used) setPhoneUrl(used); // shows the address as it was understood (a missing colon, https or /video is fixed for you)
      setPhone({ id, status: 'connecting', workers: [], analysed: 0, pushed: 0, repeats: 0 });
    } catch (e) { setError(e.message); }
  };
  const stopPhone = async () => {
    if (!phone?.id) return;
    try { await postJson(`/live/${phone.id}/stop`, {}); } catch { /* it ends on its own */ }
    setPhone((p) => p && { ...p, status: 'stopped' });
  };
  const rotatePhone = async () => {
    if (!phone?.id) return;
    try { const j = await postJson(`/live/${phone.id}/rotate`, { degrees: 90 }); setPhone((p) => p && { ...p, rotation: j.rotation, autoRotate: j.autoRotate }); } catch (e) { setError(e.message); }
  };
  useEffect(() => {
    if (!phone?.id || !['connecting', 'live'].includes(phone.status)) return undefined;
    const t = setInterval(() => call(`/live/${phone.id}`).then((j) => {
      setPhone(j);
      if (j.analysed > checks.current) { checks.current = j.analysed; raise(j.workers, live.current.location); }
    }).catch((e) => setError(e.message)), 1200);
    return () => clearInterval(t);
  }, [phone?.id, phone?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const phoneRef = useRef(null);
  phoneRef.current = phone;
  const attached = useRef(new Set()); // a camera running elsewhere is picked up once, so it cannot pull the page back to Phone after the person chose another input
  useEffect(() => {
    if (!sectorLock) return undefined;
    const look = () => fetch(`${DETECTOR}/live?sector=${sectorLock}`, { headers: { authorization: `Bearer ${session.get()?.token || ''}` } })
      .then((r) => r.json()).then((list) => {
        const running = Array.isArray(list) && list.find((x) => ['connecting', 'live'].includes(x.status));
        if (running && !attached.current.has(running.id) && !(phoneRef.current && ['connecting', 'live'].includes(phoneRef.current.status))) { attached.current.add(running.id); checks.current = running.analysed || 0; setPhone(running); setMode('phone'); }
      }).catch(() => {});
    look();
    const t = setInterval(look, 4000);
    return () => clearInterval(t);
  }, [sectorLock]); // eslint-disable-line react-hooks/exhaustive-deps
  // ONE INPUT AT A TIME. Upload, Laptop camera and Phone camera are never on together:
  //   Phone on   -> the laptop camera is off and upload is off;
  //   Laptop on  -> the phone camera is stopped and upload is off;
  //   Upload on  -> both cameras are off.
  // Changing the input switches the others off and clears what the previous one was showing.
  const firstInput = useRef(true);
  useEffect(() => {
    if (firstInput.current) { firstInput.current = false; return; }
    setJob(null); setResult(null); setVideoUrl(''); setSent(''); setError(''); setAccident(null);   // nothing from the input that was just turned off stays on screen
    if (mode !== 'camera') { stopCamera(); setAuto(false); }                                          // the laptop camera and its continuous watching
    if (mode !== 'phone' && phone) {                                                                   // the phone camera
      if (['connecting', 'live'].includes(phone.status)) stopPhone();
      setPhone(null);
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps
  const busyNow = busy || !up || job?.status === 'running' || job?.status === 'uploading';

  // ---- camera ----------------------------------------------------------------------------------
  const stopCamera = () => { stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null; };
  useEffect(() => {
    if (mode !== 'camera') { stopCamera(); setAuto(false); return undefined; }
    setCamError('');
    if (!navigator.mediaDevices?.getUserMedia) { setCamError('This browser cannot open a camera on this address. Use the upload button instead.'); return undefined; }
    navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 } }, audio: false })
      .then((s) => { stream.current = s; if (video.current) video.current.srcObject = s; })
      .catch((e) => setCamError(`Could not open the camera: ${e.message}. Allow camera access, or use the upload button.`));
    return stopCamera;
  }, [mode]);
  const grab = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return null;
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    return c.toDataURL('image/jpeg', 0.9);
  };
  useEffect(() => {
    if (!auto) return undefined;
    const t = setInterval(() => { if (!live.current.busy) { const image = grab(); if (image) check(image, 'camera frame'); } }, 5000);
    return () => clearInterval(t);
  }, [auto]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- video progress; the caught people are sent on automatically when it finishes -----------------
  const sendVideo = async (id) => {
    setBusy(true); setError('');
    try { const r = await postJson(`/video/${id}/push`, { location: live.current.location }); setSent(`Sent to the supervisor: ${r.created} new case(s)${r.repeats ? `, ${r.repeats} already caught today (count raised)` : ''}${r.accidents ? `, ${r.accidents} accident alert(s)` : ''}.`); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    if (!job?.id || job.status !== 'running') return undefined;
    const t = setInterval(() => call(`/video/${job.id}`).then((j) => { setJob(j); if (j.status === 'done' && j.incidents.length) sendVideo(j.id); }).catch((e) => setError(e.message)), 1500);
    return () => clearInterval(t);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // As the uploaded video plays, call out each person at the moment they were caught.
  const onPlay = (e) => {
    if (!job?.incidents?.length) return;
    const t = e.currentTarget.currentTime;
    const fresh = job.incidents.filter((i) => i.timeS <= t && !announced.current.has(`${i.workerId}-${i.item}-${i.timeS}`));
    if (!fresh.length) return;
    fresh.forEach((i) => announced.current.add(`${i.workerId}-${i.item}-${i.timeS}`));
    // A worker who is down is an accident alert: siren, a spoken warning and a banner, and the report goes to the supervisor with the video's results.
    const ALARM = ['WORKER DOWN', 'OBJECT NEAR WORKER', 'OBJECT HIT WORKER'];
    const down = fresh.filter((i) => ALARM.includes(i.item));
    if (down.length) {
      const venue = [live.current.sectorName, live.current.location].filter(Boolean).join(' · ') || 'the site';
      const who = down[0].person ? `${down[0].person}` : 'a worker';
      const hit = down.find((i) => i.item === 'OBJECT HIT WORKER');
      const near = down.find((i) => i.item === 'OBJECT NEAR WORKER');
      const text = hit ? `DANGER at ${venue}: an object is hitting a worker.` : near ? `DANGER at ${venue}: an object is falling close to a worker.` : `ACCIDENT DETECTED at ${venue}: ${who} is down.`;
      setAccident({ text, at: Date.now() });
      sirenFor(4000);
      if (live.current.voiceOn) speak(hit || near ? `Danger. Object falling at ${venue}. Move away. Send help.` : `Accident detected at ${venue}. ${who} is down. Send help.`);
    }
    const due = fresh.filter((i) => i.kind === 'PPE');
    if (!due.length) return;
    const people = {};
    due.forEach((i) => {
      const key = i.personId || `w${i.workerId}`;
      const p = people[key] || (people[key] = { id: key, status: 'VIOLATION', missing: [], identity: i.personId ? { employeeId: i.personId, name: i.person } : null });
      p.missing.push(i.kind === 'PPE' ? `NO ${i.item.toUpperCase()}` : i.item);
    });
    raise(Object.values(people), live.current.location);
  };
  const byWorker = {};
  (job?.incidents || []).filter((i) => i.kind === 'PPE').forEach((i) => { const key = i.personId || `w${i.workerId}`; (byWorker[key] = byWorker[key] || []).push(i); });
  const off = busy || !up;

  return (
    <>
      <PageHead title={title} sub="Upload a photo or a video, or open a live camera. Everything else is automatic: anyone caught without the required gear is called out and sent to the supervisor.">
        <Chip tone={up ? 'ok' : up === false ? 'bad' : ''}>Detector {up ? 'running' : up === false ? 'not running' : 'checking'}</Chip>
      </PageHead>
      {up === false && <div className="err">The detector service is not running. Start it with <span className="mono">npm run detector</span>, or run <span className="mono">python detector_service.py</span> in the ppe-detection folder.</div>}
      {accident && <div className="alertbar" role="alert"><span className="alertbar-dot" /><div><b>{accident.text}</b><br /><span className="small">The accident report has been sent to the supervisor. A camera can say a worker is down, not why.</span></div><span style={{ flex: 1 }} /><button className="alt sm" onClick={() => setAccident(null)}>Close</button></div>}
      {banner && <div className={`alertbar ${banner.kind}`} role="alert"><span className="alertbar-dot" /><div><b>SAFETY ALERT</b><br />{banner.text}</div></div>}

      <div className="stat-strip">
        <div><b>{caughtTotal}</b><span>people called out this session</span></div>
        <div><b>{log.length}</b><span>announcements</span></div>
        <div><b>{voiceOn ? 'On' : 'Off'}</b><span>voice alerts</span></div>
        <div><b>{sector ? sector.name : '—'}</b><span>sector being watched</span></div>
      </div>

      <div className="grid g2">
        <section className="card">
          <h3 style={{ marginBottom: '.5rem' }}>{sectorLock ? '1. Your kind of work' : '1. Choose the kind of work'}</h3>
          {!sectors.length && <div className="err">No sectors found. Is the API running?</div>}
          <div className="sector-pick" role="radiogroup" aria-label="Sector">
            {(sectorLock ? sectors.filter((s) => s.id === sectorLock) : sectors).map((s) => (
              <button key={s.id} type="button" role="radio" aria-checked={s.id === sector?.id} className={`sector-card ${s.id === sector?.id ? 'on' : ''}`} onClick={() => !sectorLock && pickSector(s.id)}>
                <b>{s.name}</b>
                <span>{s.requiredItems.join(' · ')}</span>
              </button>
            ))}
          </div>
          {sector && <p className="small muted" style={{ margin: '.1rem 0 1rem' }}>{sector.conditionClass ? `${sector.conditionClass}. ` : ''}Required: {required.join(', ')}.{location ? ` Cases are shown at ${location}.` : ''} The supervisor sets these.</p>}
          <h3 style={{ marginBottom: '.5rem' }}>2. Give it a picture</h3>

          <div className="source-switch" role="tablist" aria-label="Where the picture comes from">
            {[['upload', 'Upload', 'photo or video'], ['camera', 'Laptop camera', 'this computer'], ['phone', 'Phone camera', 'same WiFi']].map(([k, label, sub]) => (
              <button key={k} type="button" role="tab" aria-selected={mode === k} className={mode === k ? 'on' : ''} onClick={() => setMode(k)}><b>{label}</b><span>{sub}</span></button>
            ))}
          </div>
          <p className="small muted" style={{ margin: '-.5rem 0 .8rem' }}>Only one input is on at a time. Choosing another turns the current one off.</p>
          {mode === 'upload' && (
            <div className={`dropzone ${drag ? 'drag' : ''} ${busyNow ? 'off' : ''}`}
              onDragOver={(e) => { e.preventDefault(); if (!busyNow) setDrag(true); }} onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busyNow) takeFile(e.dataTransfer.files?.[0]); }}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>
              <b>Drop a photo or a video here</b>
              <span className="muted small">or</span>
              <label htmlFor="up" className={`btn ${busyNow ? 'disabled' : ''}`}>Choose a file</label>
              <input id="up" type="file" accept="image/*,video/*" onChange={upload} disabled={busyNow} hidden />
              <span className="muted small">Photos and videos (a video can be up to 400 MB). Each person caught is sent to the supervisor by itself.</span>
              <div className="actions" style={{ marginTop: 6, justifyContent: 'center', alignItems: 'center' }} onClick={(e) => e.stopPropagation()}>
                <label htmlFor="vs" className="small muted">Video speed</label>
                <select id="vs" value={speed} disabled={busyNow} onChange={(e) => { setSpeed(e.target.value); try { localStorage.setItem('siteguard.speed', e.target.value); } catch { /* not remembered */ } }}>
                  <option value="turbo">Turbo: every 6th frame, smaller picture</option>
                  <option value="fast">Fast: every 4th frame, smaller picture</option>
                  <option value="balanced">Balanced: every 2nd frame</option>
                  <option value="thorough">Thorough: full picture size</option>
                </select>
                <label htmlFor="ve" className="small muted">or check every</label>
                <input id="ve" type="number" min="1" max="10" value={every} disabled={busyNow} placeholder="auto" onChange={(e) => setEvery(e.target.value)} style={{ width: 70 }} />
                <span className="small muted">frame(s)</span>
              </div>
            </div>
          )}
          {mode === 'camera' && (
            <>
              <video ref={video} autoPlay playsInline muted style={{ width: '100%', background: '#0f1b28', borderRadius: 12, minHeight: 220 }} />
              {camError && <div className="err">{camError}</div>}
              <div className="actions"><button className="go" disabled={off} onClick={() => { const image = grab(); if (image) check(image, 'camera frame'); }}>Check this frame</button>
                <label className="inline"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Watch continuously (every 5 s)</label></div>
            </>
          )}
          {mode === 'phone' && (
            <div>
              <details className="fineprint" open={!phone} style={{ marginTop: 0 }}>
                <summary>How to connect your phone (same WiFi)</summary>
                <ol className="steps" style={{ maxWidth: 'none' }}>
                  <li>Put the phone and this computer on the same WiFi.</li>
                  <li>Android: install the free app "IP Webcam", tap "Start server", and read the address it shows, such as <span className="mono">http://192.168.1.5:8080</span>. Add <span className="mono">/video</span> at the end.</li>
                  <li>iPhone: use any IP-camera app that shows an http or rtsp address.</li>
                  <li>Paste the address below and press Start. Only cameras on your own network are accepted.</li>
                </ol>
              </details>
              <div className="actions">
                <input value={phoneUrl} onChange={(e) => setPhoneUrl(e.target.value)} placeholder="http://192.168.1.5:8080/video" aria-label="Camera address" style={{ flex: 1, minWidth: 200 }} disabled={phoneRunning} />
                {phoneRunning ? <><button className="alt" onClick={stopPhone}>Stop</button> <button className="alt" onClick={rotatePhone} title="Turn the picture a quarter turn if it is sideways (it also turns itself when it can see people)">Rotate</button></> : <button className="go" disabled={off || !phoneUrl.trim()} onClick={startPhone}>Start watching</button>}
              </div>
              {phone?.status === 'connecting' && <p className="muted small">Connecting to the phone…</p>}
              {phone?.status === 'error' && <Err text={phone.error} />}
            </div>
          )}
          <details className="fineprint">
            <summary>How names, counting and accuracy work</summary>
            <p>Names, roles and IDs are made up and belong to nobody. Someone whose face is not clear is still given a made-up name for that footage, so it does not mean the system knows who they are.</p>
            <p>A person is caught at most once a day: if caught again the same day, only the catch count goes up.</p>
            <p>Gloves, boots and goggles use a second model whose accuracy has not been measured. The welding and falling-object watches use motion only and have not been measured on real footage. See <a href="http://localhost:3002/about">About accuracy</a>.</p>
          </details>
        </section>

        <div>
          <section className="card">
            <h3>3. Result {voiceSwitch}</h3>
            {busy && !job && <p className="muted">Checking…</p>}
            <Err text={error} />

            {mode === 'phone' && phone?.id && (
              <>
                <div className="live-wrap">
                  <img src={`${DETECTOR}/stream/${phone.id}.mjpg`} alt="Live picture from the phone camera" style={{ width: '100%', borderRadius: 12, background: '#0f1b28', minHeight: 200 }} />
                  {voiceSwitch}
                </div>
                <p className="small muted" style={{ margin: '.4rem 0' }}>{phone.status === 'live' ? `Live. Checked ${phone.analysed} time${phone.analysed === 1 ? '' : 's'}${phone.pushed || phone.repeats ? `, ${phone.pushed} new case(s) sent to the supervisor${phone.repeats ? `, ${phone.repeats} repeat catches` : ''}` : ''}.` : phone.status === 'connecting' ? 'Connecting…' : phone.status === 'stopped' ? 'Stopped.' : ''}</p>
                {phone.workers?.length > 0 && <><Scene workers={phone.workers} /><WorkersTable workers={phone.workers} /></>}
              </>
            )}
            {!(mode === 'phone' && phone?.id) && !job && (!result ? !busy && <div className="empty"><b>Nothing checked yet</b><ol className="steps"><li>Pick the kind of work.</li><li>Drop in a photo or video, or open the live camera.</li><li>See who is missing gear. They are sent to the supervisor and, if voice is on, called out.</li></ol></div> : (
              <>
                <img src={result.annotated} alt="Annotated result" style={{ width: '100%', borderRadius: 12 }} />
                {result.objects > 0 && <p className="small muted" style={{ marginTop: '.5rem' }}>{result.objects} box{result.objects > 1 ? 'es were' : ' was'} judged an object, not a worker (shown in grey), and never flagged.</p>}
                <Scene workers={result.workers} />
                <WorkersTable workers={result.workers} />
                {sent && <div className="note info" style={{ marginTop: '.8rem' }}>{sent}</div>}
              </>
            ))}

            {job && (
              <>
                <p><b>{job.name}</b> {job.status === 'running' && <Chip tone="warn">checking</Chip>}{job.status === 'uploading' && <Chip tone="warn">uploading</Chip>}{job.status === 'done' && <Chip tone="ok">checked</Chip>}{job.status === 'error' && <Chip tone="bad">failed</Chip>}</p>
                {(job.status === 'running' || job.status === 'uploading') && <div className="bar-track" style={{ height: 12 }}><div className="bar-fill" style={{ width: `${job.total ? Math.round((job.done / job.total) * 100) : 4}%` }} /></div>}
                {job.status === 'error' && <Err text={job.error} />}
                {job.status === 'done' && (
                  <>
                    {videoUrl && (
                      <>
                        <div className="tabs" style={{ marginBottom: '.4rem' }}>{[[false, 'With detections (boxes, violations, worker down)'], [true, 'Original']].map(([k, label]) => <button key={String(k)} className={showOriginal === k ? 'on' : ''} onClick={() => setShowOriginal(k)}>{label}</button>)}</div>
                        <video key={showOriginal ? 'o' : 'a'} src={showOriginal ? videoUrl : `${DETECTOR}/files/${job.id}/annotated.mp4`} controls onTimeUpdate={onPlay} style={{ width: '100%', borderRadius: 12, background: '#000', maxHeight: 360 }} />
                      </>
                    )}
                    <p className="small muted" style={{ marginTop: '.4rem' }}>Press play: the video shows each worker's verdict. Each person is called out when the video reaches the moment they were caught, and a worker who is down sounds the alarm.</p>
                    {!Object.keys(byWorker).length ? <div className="empty">No violations found in this video.</div> : (
                      <div className="grid" style={{ gap: '.7rem' }}>{Object.entries(byWorker).map(([key, found]) => (
                        <div key={key} className="card" style={{ margin: 0, padding: '.7rem', display: 'flex', gap: '.9rem', alignItems: 'center' }}>
                          <img className="thumb" style={{ width: 96, height: 72 }} src={`${DETECTOR}/files/${job.id}/${found[0].evidence}`} alt={found[0].person || `Employee ${found[0].workerId}`} />
                          <div><b>{found[0].person || `Employee ${found[0].workerId}`}</b> {found[0].personId && <span className="mono small muted">{found[0].personId}</span>}<br />
                            <span style={{ color: 'var(--bad)', fontWeight: 650 }}>{[...new Set(found.map((i) => (i.kind === 'PPE' ? `NO ${i.item.toUpperCase()}` : i.item)))].join(', ')}</span><br />
                            <span className="small muted">first at {found[0].timeS}s{[...new Set(found.map((i) => i.workerId))].length > 1 ? `, one person seen as workers ${[...new Set(found.map((i) => i.workerId))].join(', ')}` : ''}</span></div>
                        </div>
                      ))}</div>
                    )}
                    {(job.incidents || []).some((i) => i.kind !== 'PPE') && (
                      <div className="note" style={{ marginTop: '.6rem' }}><b>Other events in this video</b>
                        {(job.incidents || []).filter((i) => i.kind !== 'PPE').map((i, n) => <div key={n} className="small">{i.timeS}s · <b>{i.item}</b>: {i.detail}</div>)}
                      </div>
                    )}
                    <div className="actions"><a className="btn alt" style={{ textDecoration: 'none', color: 'var(--ink)', background: '#fff', border: '1px solid #cfd6df' }} href={`${DETECTOR}/files/${job.id}/annotated.mp4`} download>Annotated video</a></div>
                    {sent && <div className="note info" style={{ marginTop: '.8rem' }}>{sent}</div>}
                  </>
                )}
              </>
            )}
          </section>

          <section className="card">
            <h3>Live alerts {log.length > 0 && <button className="link" onClick={() => setLog([])}>Clear</button>}</h3>
            {!log.length ? <p className="muted small">Nothing yet. When someone is caught without gear, the announcement appears here{voiceOn ? '' : ' (turn on voice alerts to hear it)'}.</p>
              : <div className="loglist">{log.map((e) => (
                <div key={e.id} className={`logrow ${e.kind}`}><span className="mono small">{clock(e.at)}</span><span>{e.text}</span><Chip tone="warn">spoken</Chip></div>
              ))}</div>}
          </section>
          {extraRight}
        </div>
      </div>
    </>
  );
}
