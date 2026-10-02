import { useRef, useState } from "react";
import { validDate } from "../utils/dates";

function monthDate(year: number, index: number, day = 1) {
  const date = new Date();
  date.setFullYear(year, index, day);
  date.setHours(0, 0, 0, 0);
  return date;
}

export default function DateInput({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  const today = new Date();
  const initial = validDate(value) ? new Date(`${value}T00:00:00`) : today;
  const [month, setMonth] = useState({ year: initial.getFullYear(), index: initial.getMonth() });
  const popup = useRef<HTMLDetailsElement>(null);
  const toggle = useRef<HTMLElement>(null);
  const first = monthDate(month.year, month.index).getDay();
  const days = monthDate(month.year, month.index + 1, 0).getDate();
  const caption = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(monthDate(month.year, month.index));
  function shift(amount: number) {
    const date = monthDate(month.year, month.index + amount);
    if (date.getFullYear() >= 1 && date.getFullYear() <= 9999) setMonth({ year: date.getFullYear(), index: date.getMonth() });
  }
  function choose(date: string) {
    onChange(date);
    if (popup.current) popup.current.open = false;
    toggle.current?.focus();
  }
  return <div className="date-input" onKeyDown={event => {
    if (event.key === "Escape" && popup.current?.open) { popup.current.open = false; toggle.current?.focus(); }
  }}>
    <input id={id} aria-label={label} type="text" placeholder="YYYY-MM-DD" value={value} maxLength={10}
      aria-invalid={value !== "" && !validDate(value)} onChange={event => onChange(event.target.value)} />
    <details ref={popup} className="calendar-popup" onToggle={event => {
      if (event.currentTarget.open && validDate(value)) {
        const date = new Date(`${value}T00:00:00`);
        setMonth({ year: date.getFullYear(), index: date.getMonth() });
      }
    }}>
      <summary ref={toggle} aria-label={`Choose ${label.toLowerCase()}`}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 5h16v16H4z M8 2v6 M16 2v6 M4 10h16" /></svg></summary>
      <div className="calendar" role="group" aria-label={`${label} calendar`}>
        <div className="calendar-header"><button type="button" aria-label="Previous month" onClick={() => shift(-1)}>‹</button><span aria-live="polite">{caption}</span><button type="button" aria-label="Next month" onClick={() => shift(1)}>›</button></div>
        <div className="calendar-days">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(day => <span key={day}>{day}</span>)}
          {Array.from({ length: first }, (_, index) => <span key={`blank-${index}`} />)}
          {Array.from({ length: days }, (_, index) => {
            const day = index + 1;
            const date = `${String(month.year).padStart(4, "0")}-${String(month.index + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            return <button type="button" key={day} aria-label={date} aria-pressed={value === date} onClick={() => choose(date)}>{day}</button>;
          })}
        </div>
        <div className="calendar-footer"><button type="button" onClick={() => {
          choose(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`);
        }}>Today</button><button type="button" onClick={() => choose("")}>Clear</button></div>
      </div>
    </details>
  </div>;
}
