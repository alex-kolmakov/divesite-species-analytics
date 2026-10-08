import { creditAuthor } from '../credit';
import type { CreditedImage } from '../credit';

export default function ImageCredit({ image }: { image: CreditedImage }) {
    if (!image.image_url) return null;
    const author = creditAuthor(image);
    return (
        <p className="image-credit">
            Photo:{' '}
            {image.image_page_url ? (
                <a href={image.image_page_url} target="_blank" rel="noreferrer">{author}</a>
            ) : author}
            {image.image_license && (
                <>
                    {' · '}
                    {image.image_license_url ? (
                        <a href={image.image_license_url} target="_blank" rel="noreferrer">{image.image_license}</a>
                    ) : image.image_license}
                </>
            )}
        </p>
    );
}
