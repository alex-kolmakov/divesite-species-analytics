// The letter D above the waterline and its reflection below, broken into ripples.
// public/icon.svg is the same drawing; public/favicon.svg is the simpler one for browser tabs.
const D = 'M20 8h12c8 0 13 4 13 10.5s-5 10.5-13 10.5H20z M28 14v9h4c3 0 5-2 5-4.5s-2-4.5-5-4.5z';

export default function Logo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" role="img" aria-label="Dive Diversity">
      <rect width="64" height="64" rx="14" fill="#0f172a" />
      <path d={D} fill="#f1f5f9" fillRule="evenodd" />
      <rect x="10" y="31" width="44" height="2.5" rx="1.25" fill="#06d6a0" />
      <clipPath id="logo-ripple-0">
        <rect y="35.5" width="64" height="5.5" />
      </clipPath>
      <g clipPath="url(#logo-ripple-0)" opacity="0.8">
        <path d={D} fill="#06d6a0" fillRule="evenodd" transform="translate(0 64) scale(1 -1)" />
      </g>
      <clipPath id="logo-ripple-1">
        <rect y="43.5" width="64" height="4.5" />
      </clipPath>
      <g clipPath="url(#logo-ripple-1)" opacity="0.6">
        <path d={D} fill="#06d6a0" fillRule="evenodd" transform="translate(2 64) scale(1 -1)" />
      </g>
      <clipPath id="logo-ripple-2">
        <rect y="50.5" width="64" height="3.5" />
      </clipPath>
      <g clipPath="url(#logo-ripple-2)" opacity="0.4">
        <path d={D} fill="#06d6a0" fillRule="evenodd" transform="translate(-2 64) scale(1 -1)" />
      </g>
    </svg>
  );
}
