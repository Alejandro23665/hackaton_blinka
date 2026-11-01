/** Iconos lineales (trazo 1.75, 24x24, puntas redondeadas): un único estilo, sin dependencias. */
const PATHS = {
  arrowUpRight: 'M7 17 17 7M8 7h9v9',
  check: 'm5 12.5 4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6 6 18',
  alert: 'M12 8v5m0 3.5h.01M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.8L13.7 3.9a2 2 0 0 0-3.4 0Z',
  plus: 'M12 5v14M5 12h14',
  refresh: 'M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4m-4 5a8 8 0 0 0 14.9 3.5M20 20v-4h-4',
  inbox: 'M3 13h5l1.5 3h5l1.5-3h5M5.5 5h13l2.5 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5l2.5-8Z',
  shield: 'M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6L12 3Z',
  store: 'M4 9h16l-1.5-5h-13L4 9Zm0 0v10a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9M9 20v-6h6v6',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6m-6 4h4',
  grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  bot: 'M12 4v3m-5 3h10a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2Zm2.5 4.5h.01m4.99 0h.01',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0',
  chevronRight: 'm9 6 6 6-6 6',
  wallet: 'M4 7a2 2 0 0 1 2-2h11a1 1 0 0 1 1 1v2M4 7v11a2 2 0 0 0 2 2h13a1 1 0 0 0 1-1v-3M4 7a2 2 0 0 0 2 2h13a1 1 0 0 1 1 1v3m0 0h-4a1.5 1.5 0 0 0 0 3h4',
  code: 'm9 8-4 4 4 4m6-8 4 4-4 4',
  upload: 'M12 15V4m0 0L8 8m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3',
  sparkles: 'M12 4l1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6L12 4Zm6 10 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14Z',
  external: 'M14 4h6v6m0-6-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4',
  pencil: 'M4 20h4L19 9a2.83 2.83 0 0 0-4-4L4 16v4Zm9.5-13.5 4 4',
  download: 'M12 4v11m0 0-4-4m4 4 4-4M5 19h14',
  list: 'M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01',
  arrowLeft: 'M19 12H5m6-6-6 6 6 6',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 3-4.35-4.35',
  image: 'M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm-1 12 4.5-4.5L13 16l2.5-2.5L20 18M15 8.5h.01',
  layers: 'M12 3 3 8l9 5 9-5-9-5Zm-9 9 9 5 9-5',
  chart: 'M4 20h16M7 16v-5m5 5V8m5 8v-3',
  trash: 'M4 7h16M10 11v6m4-6v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2',
  home: 'M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1v-8.5Z',
  scan: 'M4 8V5a1 1 0 0 1 1-1h3m8 0h3a1 1 0 0 1 1 1v3m0 8v3a1 1 0 0 1-1 1h-3m-8 0H5a1 1 0 0 1-1-1v-3m4-4 2.5 2.5L16 9',
  users: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm-6 9a6 6 0 0 1 12 0m1-16.5a3.5 3.5 0 0 1 0 7m2 9.5h3a6 6 0 0 0-3.5-5.5',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3m-5-3 5-5-5-5m5 5H4',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-2.5-11.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6m0 3h.01',
  eyeOff: 'M3 3l18 18M10.6 5.1A9.8 9.8 0 0 1 12 5c5 0 8.5 4.5 9.5 7a13 13 0 0 1-2.4 3.6M6.6 6.6C4.4 8 3 10.2 2.5 12c1 2.5 4.5 7 9.5 7 1.8 0 3.4-.6 4.8-1.4M9.9 9.9a3 3 0 0 0 4.2 4.2',
  notEqual: 'M5 9h14M5 15h14M16 5 8 19',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  checkCircle: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-4-9 2.8 2.8L16 9.5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v4l3 2',
  loader: 'M12 3a9 9 0 1 0 9 9',
  pause: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-2-12v6m4-6v6',
  minus: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-4-9h8',
  copy: 'M9 9h10v10H9zM5 15V5h10',
  bolt: 'M13 3 5 13.5h6L10 21l8-10.5h-6L13 3Z',
  mail: 'M4 6h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm-1 1 9 6.5L21 7',
  calendar: 'M5 6h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm-1 4h16M8 4v4m8-4v4',
  phone: 'M5 4h3.5l1.5 4.5-2 1.5a11 11 0 0 0 6 6l1.5-2 4.5 1.5V19a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1Z',
}

export default function Icon({ name, size = 18, className = '', strokeWidth = 1.75 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
