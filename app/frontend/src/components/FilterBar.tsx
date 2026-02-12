import './FilterBar.css';

interface Props {
    active: string;
    onChange: (value: string) => void;
}

const FILTERS = [
    { value: 'all', label: 'All', icon: '' },
    { value: 'endangered', label: '⚠️', title: 'Endangered' },
    { value: 'invasive', label: '🦠', title: 'Invasive' },
    { value: 'normal', label: 'Normal', icon: '' },
];

export default function FilterBar({ active, onChange }: Props) {
    return (
        <div className="filter-bar">
            {FILTERS.map(f => (
                <button
                    key={f.value}
                    className={`filter-chip${active === f.value ? ' active' : ''}`}
                    onClick={() => onChange(f.value)}
                    title={'title' in f ? f.title : f.label}
                >
                    {f.label}
                </button>
            ))}
        </div>
    );
}
