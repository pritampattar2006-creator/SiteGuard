import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api.js';

// Ctrl+K (or Cmd+K): jump to any page, find an employee, switch theme or sign out, from the keyboard.
export function CommandPalette({ nav, user, theme, onTheme, onLogout }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [at, setAt] = useState(0);
  const [people, setPeople] = useState([]);
  const input = useRef(null);
  const go = useNavigate();

  useEffect(() => {
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((v) => !v); }
      else if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', key);
    const ask = () => setOpen(true);
    window.addEventListener('siteguard:palette', ask);
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('siteguard:palette', ask); };
  }, []);
  useEffect(() => {
    if (!open) return;
    setText(''); setAt(0);
    setTimeout(() => input.current?.focus(), 0);
    if (user?.role === 'supervisor') api('/api/employees').then((l) => setPeople(Array.isArray(l) ? l : [])).catch(() => {});
  }, [open, user?.role]);

  const items = useMemo(() => [
    ...nav.map((n) => ({ label: `Go to ${n.label}`, run: () => go(n.to) })),
    ...people.map((p) => ({ label: `Employee: ${p.name} (${p.employeeId})`, run: () => go(`/employees/${p.id}`) })),
    { label: theme === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme', run: onTheme },
    ...(onLogout ? [{ label: 'Sign out', run: onLogout }] : []),
  ].filter((i) => i.label.toLowerCase().includes(text.toLowerCase())).slice(0, 12), [nav, people, text, theme]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;
  const pick = (i) => { setOpen(false); i?.run(); };
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setAt((a) => Math.min(items.length - 1, a + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setAt((a) => Math.max(0, a - 1)); }
    else if (e.key === 'Enter') pick(items[at]);
  };
  return (
    <div className="palette-back" onMouseDown={() => setOpen(false)}>
      <div className="palette" role="dialog" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
        <input ref={input} value={text} onChange={(e) => { setText(e.target.value); setAt(0); }} onKeyDown={onKey} placeholder="Type a page, an employee or a command" aria-label="Search" />
        <div className="palette-list" role="listbox">
          {items.map((i, n) => <button key={i.label} role="option" aria-selected={n === at} className={n === at ? 'on' : ''} onMouseEnter={() => setAt(n)} onClick={() => pick(i)}>{i.label}</button>)}
          {!items.length && <p className="muted small" style={{ padding: '.6rem .9rem' }}>Nothing matches.</p>}
        </div>
        <p className="small muted" style={{ margin: 0, padding: '.4rem .9rem' }}>Up and down to choose, Enter to open, Esc to close.</p>
      </div>
    </div>
  );
}

export function Toasts() {
  const [list, setList] = useState([]);
  useEffect(() => {
    const on = (e) => {
      const id = Math.random();
      setList((l) => [...l.slice(-3), { id, text: e.detail }]);
      setTimeout(() => setList((l) => l.filter((t) => t.id !== id)), 3500);
    };
    window.addEventListener('siteguard:toast', on);
    return () => window.removeEventListener('siteguard:toast', on);
  }, []);
  return <div className="toasts" role="status" aria-live="polite">{list.map((t) => <div key={t.id} className="toast">{t.text}</div>)}</div>;
}
