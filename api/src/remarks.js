// A short plain-English remark written from the facts of a case. It is a template, not a guess: every statement in it comes from
// the case itself (who, what was missing, where, when, how many times, how many earlier violations). A supervisor can edit it.
import { itemsOf } from './daily.js';

const list = (items) => (items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`);

export function makeRemark({ v, employee, prior = 0, proposeAt = 3 }) {
  const who = employee ? `${employee.name}${employee.jobRole ? ` (${employee.jobRole})` : ''}` : (v.workerRef || 'A worker');
  const items = itemsOf(v.missing).map((i) => i.replace(/^NO /, '').toLowerCase()).filter((i) => i !== 'unknown');
  const unclear = !items.length || items.includes('unclear');
  const when = new Date(v.occurredAt).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata' });
  const where = v.location ? ` at ${v.location}` : '';
  const parts = [unclear ? `${who} may be missing required safety gear${where} (${when}), but the picture is not clear.` : `${who} was seen without ${list(items)}${where} on ${when}.`];
  if ((v.catches || 1) > 1) parts.push(`Caught ${v.catches} times that day.`);
  if (employee) {
    parts.push(prior === 0 ? 'First violation in the last 30 days.' : `${prior} earlier violation${prior > 1 ? 's' : ''} in the last 30 days, so this is number ${prior + 1}.`);
    if (prior + 1 >= proposeAt) parts.push('This reaches the penalty-review threshold.');
  }
  if (/not sure|unsure/i.test(v.reason || '')) parts.push('The detector was unsure, so please check the picture.');
  return parts.join(' ');
}
