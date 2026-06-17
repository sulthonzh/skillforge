// SkillForge logo — an anvil/spark hybrid mark.
// Uses currentColor so it inherits the text color and adapts to theme.

export function LogoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {/* rounded tile background */}
      <rect width="32" height="32" rx="8" fill="url(#sf-grad)" />
      {/* anvil silhouette */}
      <path
        d="M7 11.5h11.5l-1.2 2.2a3 3 0 0 1-2.6 1.6h-3.9a1 1 0 0 0-.94.66l-.5 1.34h7.6l-.9 1.7a2.4 2.4 0 0 1-2.15 1.3H10.4l.55 3.2a1 1 0 0 0 .99.84h2.06v1.5H9.2a1 1 0 0 1-.99-1.16L9.3 17H7.7a.7.7 0 0 1-.64-.99l1.4-3.06A1 1 0 0 0 7.4 12H7a.5.5 0 0 1-.5-.5Z"
        fill="white"
        fillOpacity="0.95"
      />
      {/* spark above the anvil */}
      <path
        d="M22 6.5l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z"
        fill="white"
      />
      <defs>
        <linearGradient id="sf-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="hsl(250 84% 66%)" />
          <stop offset="1" stopColor="hsl(280 84% 60%)" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Logo({ withWordmark = true }: { withWordmark?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <LogoMark className="h-7 w-7" />
      {withWordmark && (
        <span className="text-[15px] font-semibold tracking-tight">SkillForge</span>
      )}
    </span>
  );
}
