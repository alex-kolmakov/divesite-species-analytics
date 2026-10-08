import type { ImageCredit } from './api/client';

export type CreditedImage = ImageCredit & { image_license_url?: string | null; image_source?: string | null };

export function creditAuthor(image: CreditedImage) {
    // Commons credits often start with their own "Photo by"; the UI already says "Photo:"
    const credit = image.image_credit?.replace(/^photo(graph)?\s*(by|:)\s*/i, '').trim();
    if (credit) return credit;
    return image.image_source === 'gbif_occurrence' ? 'via GBIF' : 'via Wikimedia Commons';
}

/** Plain-text credit, for image tooltips. */
export function creditText(image: CreditedImage) {
    return [`Photo: ${creditAuthor(image)}`, image.image_license].filter(Boolean).join(' · ');
}
