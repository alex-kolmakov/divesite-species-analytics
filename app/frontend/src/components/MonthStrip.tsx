import './MonthStrip.css';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Twelve boxes, filled for the calendar months with records (all years folded together). */
export default function MonthStrip({ months }: { months: number[] | null }) {
    const seen = new Set(months ?? []);
    return (
        <span className="month-strip" aria-label={`Seen in ${MONTHS.filter((_, i) => seen.has(i + 1)).join(', ')}`}>
            {MONTHS.map((m, i) => (
                <i key={m} className={seen.has(i + 1) ? 'on' : undefined} title={m}>{m[0]}</i>
            ))}
        </span>
    );
}
