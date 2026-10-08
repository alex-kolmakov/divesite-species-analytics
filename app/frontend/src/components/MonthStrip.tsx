import './MonthStrip.css';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * The calendar months with records (all years folded together): twelve boxes, filled for the
 * months seen. A species seen in every month gets the words instead of twelve filled boxes.
 */
export default function MonthStrip({ months }: { months: number[] | null }) {
    const seen = new Set(months ?? []);
    if (seen.size === 0) return null;
    if (seen.size === MONTHS.length) return <span className="month-strip__label">Seen all year</span>;
    return (
        <span className="month-strip" aria-label={`Seen in ${MONTHS.filter((_, i) => seen.has(i + 1)).join(', ')}`}>
            <span className="month-strip__label">Seen in</span>
            {MONTHS.map((m, i) => (
                <i key={m} className={seen.has(i + 1) ? 'on' : undefined} title={m}>{m[0]}</i>
            ))}
        </span>
    );
}
