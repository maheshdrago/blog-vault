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
