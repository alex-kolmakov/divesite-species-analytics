import { useEffect, useState } from 'react';

interface State<T> {
    key: string | null;
    data: T | null;
    error: boolean;
}

/**
 * Call `fn(...args)` whenever the arguments change; pass `null` to skip. `fn` must be stable
 * (a module-level function). A response for arguments that are no longer current is dropped.
 */
export function useAsync<A extends unknown[], T>(fn: (...args: A) => Promise<T>, args: A | null) {
    const key = args === null ? null : JSON.stringify(args);
    const [state, setState] = useState<State<T>>({ key: null, data: null, error: false });

    useEffect(() => {
        if (key === null) return;
        let cancelled = false;
        fn(...(JSON.parse(key) as A))
            .then(data => { if (!cancelled) setState({ key, data, error: false }); })
            .catch(() => { if (!cancelled) setState({ key, data: null, error: true }); });
        return () => { cancelled = true; };
    }, [fn, key]);

    const current = key !== null && state.key === key;
    return {
        data: current ? state.data : null,
        loading: key !== null && !current,
        error: current && state.error,
    };
}

export function useDebounced<T>(value: T, ms: number) {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), ms);
        return () => clearTimeout(timer);
    }, [value, ms]);
    return debounced;
}
