/**
 * Arayüzde kullanılan ikon seti.
 * Ekran görüntülerindeki ince çizgili (outline) stile uygun olarak
 * 24×24 kutu ve 1.7 çizgi kalınlığı ile yeniden çizilmiştir.
 */

type IconProps = React.SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const HomeIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 10.5 12 3.8l8.5 6.7V19a1.5 1.5 0 0 1-1.5 1.5h-3.4v-5.2H8.4v5.2H5A1.5 1.5 0 0 1 3.5 19z" />
  </Svg>
);

export const HomeFilledIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M3.5 10.4 12 3.7l8.5 6.7V19a1.6 1.6 0 0 1-1.6 1.6h-3.7v-5.4H9.8v5.4H6.1A1.6 1.6 0 0 1 4.5 19v-8.6z" />
  </svg>
);

export const BellIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M18 8.6a6 6 0 1 0-12 0c0 4.2-1.4 5.6-1.4 5.6h14.8S18 12.8 18 8.6" />
    <path d="M13.7 18a2 2 0 0 1-3.4 0" />
  </Svg>
);

export const MessageIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.5 12a7.9 7.9 0 0 1-8.5 7.9 9 9 0 0 1-3.2-.6l-4.3 1.2 1.2-3.9A7.6 7.6 0 0 1 3.5 12 7.9 7.9 0 0 1 12 4.1a7.9 7.9 0 0 1 8.5 7.9" />
    <path d="M8.6 12h6.8" />
  </Svg>
);

export const CompassIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m14.9 9.1-1.6 4.2-4.2 1.6 1.6-4.2z" />
  </Svg>
);

export const NodIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.6 20 19a1 1 0 0 1-.9 1.5H4.9A1 1 0 0 1 4 19z" />
    <path d="M9.4 14.2h5.2" />
  </Svg>
);

export const StarIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m12 3.9 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />
  </Svg>
);

export const BookmarkIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.4 4.5h11.2a.9.9 0 0 1 .9.9v14.2L12 16.1l-6.5 3.5V5.4a.9.9 0 0 1 .9-.9" />
  </Svg>
);

export const RocketIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14.6 4.6c2.6-1.3 5-1 5 1 0 2.6-1.9 5.9-4.6 8.2l.4 3.6-4 2.4-.9-4.2-3.9-1 2.3-4L5.5 9 8 5z" />
    <path d="M9.2 14.8 5.6 18.4" />
  </Svg>
);

export const SettingsIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.8 7.5h6.4M14.2 7.5h6M3.8 16.5h6M13.8 16.5h6.4" />
    <circle cx="12.3" cy="7.5" r="2.1" />
    <circle cx="11.8" cy="16.5" r="2.1" />
  </Svg>
);

export const TeknofestIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.6" y="3.6" width="6.2" height="6.2" rx="1.2" />
    <rect x="14.2" y="3.6" width="6.2" height="6.2" rx="1.2" />
    <rect x="3.6" y="14.2" width="6.2" height="6.2" rx="1.2" />
    <path d="M14.2 17.3h6.2M17.3 14.2v6.2" />
  </Svg>
);

export const PenIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M16.4 3.9a2.1 2.1 0 0 1 3 3L9 17.3l-4 1 1-4z" />
    <path d="m14.4 5.9 3 3" />
  </Svg>
);

export const PlayCircleIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M10.3 9.1v5.8l4.6-2.9z" fill="currentColor" stroke="none" />
  </Svg>
);

export const MoonIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20 13.5A8 8 0 0 1 10.5 4a8 8 0 1 0 9.5 9.5" />
  </Svg>
);

export const SearchIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="6.6" />
    <path d="m16 16 4 4" />
  </Svg>
);

export const ChevronDownIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m6.5 9.5 5.5 5.4 5.5-5.4" />
  </Svg>
);

export const ChevronUpIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m6.5 14.5 5.5-5.4 5.5 5.4" />
  </Svg>
);

export const ChevronRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m9.5 6.5 5.4 5.5-5.4 5.5" />
  </Svg>
);

export const ImageIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.6" y="4.8" width="16.8" height="14.4" rx="2.4" />
    <circle cx="8.6" cy="9.8" r="1.5" />
    <path d="m4.4 16.6 4.3-4 3.6 3.3 3-2.6 4.3 3.8" />
  </Svg>
);

export const PollIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.8" y="4.6" width="16.4" height="14.8" rx="2.4" />
    <path d="M8.4 15.6v-4M12 15.6V8.8M15.6 15.6v-2.4" />
  </Svg>
);

export const InfoIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="M12 11v5.2" />
    <circle cx="12" cy="8.2" r=".9" fill="currentColor" stroke="none" />
  </Svg>
);

export const SmileIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="M8.8 14.2a4 4 0 0 0 6.4 0" />
    <circle cx="9.3" cy="10" r=".9" fill="currentColor" stroke="none" />
    <circle cx="14.7" cy="10" r=".9" fill="currentColor" stroke="none" />
  </Svg>
);

export const CalendarIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.8" y="5.4" width="16.4" height="14" rx="2.4" />
    <path d="M3.8 9.6h16.4M8.4 3.6v3.4M15.6 3.6v3.4" />
  </Svg>
);

export const GifIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.6" y="4.8" width="16.8" height="14.4" rx="2.4" />
    <path d="M12.4 10.2a2.6 2.6 0 1 0 0 3.6M15.6 9.9v4.2M18.2 9.9h-2.6M18 12h-2.4" />
  </Svg>
);

export const GlobeIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="M3.7 12h16.6M12 3.6c2.1 2.3 3.2 5.3 3.2 8.4S14.1 18.1 12 20.4c-2.1-2.3-3.2-5.3-3.2-8.4S9.9 5.9 12 3.6" />
  </Svg>
);

export const UsersIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8.6" r="3.6" />
    <path d="M5.4 19.4a6.8 6.8 0 0 1 13.2 0" />
  </Svg>
);

export const AtIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3.4" />
    <path d="M15.4 8.6v4.6a2.7 2.7 0 0 0 5.1 0V12a8.4 8.4 0 1 0-3.3 6.7" />
  </Svg>
);

export const CloseIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m6.8 6.8 10.4 10.4M17.2 6.8 6.8 17.2" />
  </Svg>
);

export const MoreIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <circle cx="5.6" cy="12" r="1.6" />
    <circle cx="12" cy="12" r="1.6" />
    <circle cx="18.4" cy="12" r="1.6" />
  </svg>
);

export const VerifiedIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" {...p}>
    <path
      d="m12 2.4 2.4 1.9 3-.3 1 2.9 2.6 1.6-1 2.9 1 2.9-2.6 1.6-1 2.9-3-.3L12 21.6l-2.4-1.9-3 .3-1-2.9L3 15.5l1-2.9-1-2.9 2.6-1.6 1-2.9 3 .3z"
      fill="#1D9BF0"
    />
    <path
      d="m8.4 12.2 2.5 2.5 4.8-5"
      stroke="#fff"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const CommentIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.4 11.6c0 4-3.8 7.2-8.4 7.2a9.7 9.7 0 0 1-2.6-.35L4.8 20l1-3.4a6.8 6.8 0 0 1-2.2-5c0-4 3.8-7.2 8.4-7.2s8.4 3.2 8.4 7.2" />
  </Svg>
);

export const QuoteIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.4 11.4c0 3.9-3.8 7-8.4 7a9.9 9.9 0 0 1-2.4-.3L5.2 19.8l.8-3.1a6.7 6.7 0 0 1-2.4-5.3c0-3.9 3.8-7 8.4-7s8.4 3.1 8.4 7" />
    <path d="M9.6 10.2h4.8M9.6 13h3" />
  </Svg>
);

export const ChartIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 19.2V13M10 19.2V6.4M15 19.2v-8.6M20 19.2v-4" />
  </Svg>
);

export const ShareIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 15.6V4.2M8.2 7.8 12 4l3.8 3.8" />
    <path d="M5.4 13.2v5.4a1.6 1.6 0 0 0 1.6 1.6h10a1.6 1.6 0 0 0 1.6-1.6v-5.4" />
  </Svg>
);

export const HashIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5.4 9.4h13.2M4.8 14.6H18M10.4 4.4 8.6 19.6M15.4 4.4l-1.8 15.2" />
  </Svg>
);

export const EyeOffIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9.9 5.1A8.6 8.6 0 0 1 12 4.9c5 0 8.4 4.4 8.4 7.1a8.6 8.6 0 0 1-2 3.6M6.6 6.9A10 10 0 0 0 3.6 12c0 2.7 3.4 7.1 8.4 7.1a9 9 0 0 0 4-.9" />
    <path d="M10.4 10.4a2.3 2.3 0 0 0 3.2 3.2M3.6 3.6l16.8 16.8" />
  </Svg>
);

export const KeyIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="9.4" cy="9.4" r="4.4" />
    <path d="m12.6 12.6 6 6M15.4 15.4l1.8-1.8" />
  </Svg>
);

export const PipIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.4" y="5.2" width="17.2" height="13.6" rx="2.2" />
    <rect x="12.2" y="11.4" width="6.6" height="5.4" rx="1.2" fill="currentColor" stroke="none" />
  </Svg>
);

export const ExternalIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14 4.4h5.6V10M19.6 4.4 11 13" />
    <path d="M18 14v4.2a1.6 1.6 0 0 1-1.6 1.6H5.8a1.6 1.6 0 0 1-1.6-1.6V7.6A1.6 1.6 0 0 1 5.8 6H10" />
  </Svg>
);

export const ComposeIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M18.4 3.8a2 2 0 0 1 2.8 2.8L12 15.8l-3.7.9.9-3.7z" />
    <path d="M19 13.6v5a1.8 1.8 0 0 1-1.8 1.8H5.4a1.8 1.8 0 0 1-1.8-1.8V6.8A1.8 1.8 0 0 1 5.4 5h5" />
  </Svg>
);

/* ─────────── Analiz kartı ikonları ─────────── */

export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.4 19 6v6.1c0 4-2.9 7.3-7 8.5-4.1-1.2-7-4.5-7-8.5V6z" />
    <path d="m9 12 2.2 2.2L15.4 10" />
  </Svg>
);

export const ClockRewindIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.9 12a8.1 8.1 0 1 0 2.5-5.8" />
    <path d="M3.6 4.4v4.2h4.2M12 7.8V12l3 1.8" />
  </Svg>
);

export const QuestionIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="M9.7 9.4a2.4 2.4 0 1 1 3.3 2.2c-.7.3-1 .9-1 1.6v.4" />
    <circle cx="12" cy="16.6" r=".9" fill="currentColor" stroke="none" />
  </Svg>
);

export const SparkIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.6 13.7 9l5.4 1.7-5.4 1.7L12 17.8l-1.7-5.4L4.9 10.7 10.3 9z" />
    <path d="M18.4 4.2v2.8M17 5.6h2.8" />
  </Svg>
);

export const ScissorsIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="6.4" cy="6.4" r="2.4" />
    <circle cx="6.4" cy="17.6" r="2.4" />
    <path d="M8.5 8.1 19.4 18.4M19.4 5.6 8.5 15.9" />
  </Svg>
);

export const MegaphoneIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.2 10.2v3.6a1.4 1.4 0 0 0 1.4 1.4h2.2l7.6 4.2V4.6L7.8 8.8H5.6a1.4 1.4 0 0 0-1.4 1.4" />
    <path d="M18.6 9.2a4 4 0 0 1 0 5.6" />
  </Svg>
);

export const CheckCircleIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="m8.4 12.2 2.5 2.5 4.8-5" />
  </Svg>
);

export const BanIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="m6.6 6.6 10.8 10.8" />
  </Svg>
);

export const LifeBuoyIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <circle cx="12" cy="12" r="3.4" />
    <path d="m6.1 6.1 3.5 3.5M14.4 14.4l3.5 3.5M17.9 6.1l-3.5 3.5M9.6 14.4l-3.5 3.5" />
  </Svg>
);

export const RadarIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <circle cx="12" cy="12" r="4.6" />
    <path d="M12 12 18 7.4" />
    <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
  </Svg>
);

export const GavelIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m5.4 14.2 4.4-4.4M8.2 8.4l3.4-3.4 5 5-3.4 3.4z" />
    <path d="M3.6 20.4h9.2M4.6 16.4l3-3" />
  </Svg>
);

export const RefreshIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.2 12a8.2 8.2 0 1 1-2.6-6" />
    <path d="M20.4 4.2v4.4H16" />
  </Svg>
);
