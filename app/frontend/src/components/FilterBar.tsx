import './FilterBar.css';

interface Props {
    active: string;
    onChange: (value: string) => void;
}

const FILTERS = [
    { value: 'all', label: 'All' },
    { value: 'endangered', label: '⚠ Endangered' },
    { value: 'invasive', label: '🦠 Invasive' },
    { value: 'normal', label: 'Normal' },
];

export default function FilterBar({ active, onChange }: Props) {
    return (
        <div className="filter-bar">
            {FILTERS.map(f => (
                <button
                    key={f.value}
                    className={`filter-chip${active === f.value ? ' active' : ''}`}
                    onClick={() => onChange(f.value)}
                >
                    {f.label}
                </button>
            ))}
        </div>
    );
}
