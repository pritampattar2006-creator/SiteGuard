// What to say out loud when people are caught without safety gear, and how often. Plain functions, so they can be tested.
//   - One person is spoken to at most once every `personCooldownMs` (10 minutes), so the same worker is not nagged every few seconds.
//   - Only the people who broke a rule are named. There is no announcement to everyone.
export const DEFAULTS = { personCooldownMs: 10 * 60 * 1000 };

const SPOKEN = { 'NO HELMET': 'helmet', 'NO VEST': 'vest', 'NO GLOVES': 'gloves', 'NO GOGGLES': 'goggles', 'NO BOOTS': 'boots' };
const say = (item) => SPOKEN[String(item).toUpperCase()] || String(item).toLowerCase().replace(/^no /, '');
const joinWords = (words) => (words.length < 2 ? words.join('') : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`);
const firstName = (name) => String(name || '').split(/\s+/)[0];

export const newAlertState = () => ({ person: {} });

// A worker counts as caught only on a definite violation, never on "needs review".
export const isCaught = (w) => w.status === 'VIOLATION';

export function planAlerts(workers, location, state, now, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const caught = workers.filter(isCaught);
  const next = { person: { ...state.person } };
  const out = { speak: [], log: [], state: next };
  if (!caught.length) return out;
  const keyOf = (w) => w.identity?.employeeId || `${location || 'site'}|${(w.missing || []).join(',')}`;

  for (const w of caught) {
    const key = keyOf(w);
    if (now - (state.person[key] ?? -Infinity) < o.personCooldownMs) continue;
    const items = joinWords((w.missing || []).map(say));
    const text = w.identity
      ? `${firstName(w.identity.name)}, please wear your ${items}.`
      : `Attention${location ? ` at ${location}` : ''}: ${w.label || 'a worker'} is not wearing a ${items}.`;
    out.speak.push(text);
    out.log.push({ kind: 'person', text, name: w.identity?.name || '', items });
    next.person[key] = now;
  }
  return out;
}

// "7 of 10 are fully equipped; these are not wearing gear right now."
export function sceneSummary(workers) {
  const missingCount = (item) => workers.filter((w) => (w.missing || []).includes(item)).length;
  return {
    total: workers.length,
    ok: workers.filter((w) => w.status === 'COMPLIANT').length,
    review: workers.filter((w) => w.status === 'NEEDS_REVIEW').length,
    caught: workers.filter(isCaught).length,
    helmetsMissing: missingCount('NO HELMET'),
    vestsMissing: missingCount('NO VEST'),
    notWearing: workers.filter(isCaught).map((w) => ({ label: w.identity?.name || w.label || `Employee ${w.id}`, items: (w.missing || []).map(say) })),
  };
}

// ---- speaking (browser only) --------------------------------------------------------------------
export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window;

export function speak(text) {
  if (!canSpeak()) return false;
  const u = new SpeechSynthesisUtterance(text);
  const voices = window.speechSynthesis.getVoices();
  u.voice = voices.find((v) => /en-IN/i.test(v.lang)) || voices.find((v) => /^en/i.test(v.lang)) || null;
  u.rate = 0.95;
  u.volume = 1;
  window.speechSynthesis.speak(u);
  return true;
}
