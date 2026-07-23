import type { ReactNode, SVGProps } from 'react';

type IconName = 'arrow' | 'bookmark' | 'close' | 'doc' | 'folder' | 'heart' |
  'logo' | 'menu' | 'moon' | 'plus' | 'search' | 'sun' | 'trash';

const paths: Record<IconName, ReactNode> = {
  arrow: <path d="M5 12h14M14 7l5 5-5 5" />,
  bookmark: <path d="M6 3h12v18l-6-4-6 4V3Z" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  doc: <path d="M6 2h8l4 4v16H6zM14 2v5h5M9 12h6M9 16h6" />,
  folder: <path d="M3 6h7l2 2h9v11H3z" />,
  heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z" />,
  logo: <><circle cx="12" cy="12" r="9" /><path d="M12 3v18M3 12h18M5.6 5.6c3.5 3.5 9.3 3.5 12.8 0M5.6 18.4c3.5-3.5 9.3-3.5 12.8 0" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  moon: <path d="M20.5 15.2A9 9 0 1 1 8.8 3.5a7 7 0 0 0 11.7 11.7Z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" /></>,
  trash: <path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" />,
};

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 20, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" {...props}>
      {paths[name]}
    </svg>
  );
}

interface BrandIconProps extends SVGProps<SVGSVGElement> {
  size?: number;
}

export function GitHubIcon({ size = 18, ...props }: BrandIconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor"
      aria-hidden="true" {...props}>
      <path d="M12 .7A11.5 11.5 0 0 0 8.36 23.1c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.77 2.72 1.26 3.38.96.1-.75.4-1.26.74-1.55-2.57-.29-5.28-1.28-5.28-5.69 0-1.26.45-2.28 1.2-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18A11 11 0 0 1 12 6.1c.98 0 1.95.13 2.86.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.25c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z" />
    </svg>
  );
}

export function GoogleIcon({ size = 18, ...props }: BrandIconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
      aria-hidden="true" {...props}>
      <path fill="#4285f4" d="M21.35 12.23c0-.71-.06-1.4-.18-2.07H12v3.9h5.24a4.48 4.48 0 0 1-1.94 2.94v2.54h3.14c1.84-1.69 2.91-4.19 2.91-7.31Z" />
      <path fill="#34a853" d="M12 21.75c2.62 0 4.82-.87 6.44-2.21L15.3 17a5.86 5.86 0 0 1-8.72-3.08H3.33v2.62A9.73 9.73 0 0 0 12 21.75Z" />
      <path fill="#fbbc05" d="M6.58 13.92A5.85 5.85 0 0 1 6.27 12c0-.67.12-1.32.31-1.92V7.46H3.33A9.73 9.73 0 0 0 2.25 12c0 1.63.39 3.18 1.08 4.54l3.25-2.62Z" />
      <path fill="#ea4335" d="M12 6.14c1.43 0 2.72.49 3.73 1.46l2.78-2.79A9.35 9.35 0 0 0 12 2.25a9.73 9.73 0 0 0-8.67 5.21l3.25 2.62A5.8 5.8 0 0 1 12 6.14Z" />
    </svg>
  );
}
