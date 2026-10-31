// The repeat-violation policy. Pure functions, so they are easy to test.
// A violation counts only once a supervisor has confirmed it. A dismissed or still-pending one never counts.
import fs from 'node:fs';

export const COUNTED = ['Confirmed', 'Acknowledged', 'Disputed', 'Resolved'];
export const DEFAULT_POLICY = { windowDays: 30, proposeAt: 3, amount: 500, currency: 'INR', timezoneOffsetMinutes: 330 };

export function loadPolicy(file) {
  try {
    const p = JSON.parse(fs.readFileSync(file, 'utf8'));
    return { ...DEFAULT_POLICY, ...p };
  } catch {
    return { ...DEFAULT_POLICY };
  }
}

// Groups of `proposeAt` confirmed violations (oldest first, inside the window, not yet attached to a penalty)
// that now deserve one proposed penalty each.
export function newPenaltyBatches(violations, policy, now = new Date()) {
  const since = now.getTime() - policy.windowDays * 86400000;
  const open = violations
    .filter((v) => COUNTED.includes(v.status) && !v.penaltyId && new Date(v.occurredAt).getTime() >= since)
    .sort((a, b) => new Date(a.occurredAt) - new Date(b.occurredAt));
  const batches = [];
  for (let i = 0; i + policy.proposeAt <= open.length; i += policy.proposeAt) batches.push(open.slice(i, i + policy.proposeAt));
  return batches;
}
