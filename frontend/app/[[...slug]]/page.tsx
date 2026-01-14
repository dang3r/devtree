// Required for static export (production build)
// Dynamic routes (/device/*, /company/*) are handled by Cloudflare's _redirects
export function generateStaticParams() {
  return [
    { slug: [] },             // /
    { slug: ['background'] }, // /background
    { slug: ['research'] },   // /research
    { slug: ['contact'] },    // /contact
  ];
}

// Catch-all route for SPA - actual content is in layout.tsx
export default function Page() {
  return null;
}
