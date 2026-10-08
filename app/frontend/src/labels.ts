/** 'critically endangered' → 'Critically endangered' */
export function iucnLabel(category: string | null) {
    return category ? category[0].toUpperCase() + category.slice(1) : null;
}

export function invasiveHereLabel(invasiveness: 'invasive' | 'of concern' | null) {
    if (invasiveness === 'invasive') return 'Invasive here';
    if (invasiveness === 'of concern') return 'Of concern here';
    return null;
}

/** Year of an ISO date string */
export function year(date: string | null) {
    return date ? date.slice(0, 4) : null;
}

export const speciesPath = (species: string) => `/species/${encodeURIComponent(species)}`;
export const sitePath = (siteId: string) => `/divesites/${encodeURIComponent(siteId)}`;

/** The name to show for a species: the first of its common names, capitalised, else the scientific one. */
export function displayName(commonName: string | null, species: string) {
    const first = commonName?.split(/,\s*/)[0].trim();
    return first ? first[0].toUpperCase() + first.slice(1) : species;
}

/** A site title as published, minus its HTML entities and ALL CAPS. */
export function siteName(title: string) {
    const text = title.includes('&')
        ? new DOMParser().parseFromString(title, 'text/html').documentElement.textContent ?? title
        : title;
    if (text !== text.toUpperCase() || !/\p{L}{4}/u.test(text)) return text;
    return text.toLowerCase().replace(/(^|[\s\-'’(/])\p{L}/gu, c => c.toUpperCase());
}
