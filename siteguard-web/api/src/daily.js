// One violation per person per day. A person caught again the same day is a "repeat catch" on that day's case, not a new violation;
// the next day, breaking the rule again makes a new one. The day is the site's local day, so the offset is a setting.
export const dayKey = (iso, offsetMinutes = 330) => new Date(new Date(iso).getTime() + offsetMinutes * 60000).toISOString().slice(0, 10);

// "NO HELMET + NO VEST", "no helmet, no vest" and "NO VEST" all become lists of items, so they can be combined.
export const itemsOf = (text) => String(text || '').toUpperCase().split(/\s*[,+]\s*/).map((s) => s.trim()).filter(Boolean);
export const mergeItems = (a, b) => [...new Set([...itemsOf(a), ...itemsOf(b)])].join(', ');
