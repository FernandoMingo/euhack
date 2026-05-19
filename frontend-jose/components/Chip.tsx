import type { ReactNode } from "react";

type Tone = "default" | "sage" | "mist" | "peach";

const TONE_CLASS: Record<Tone, string> = {
  default: "bg-secondary text-foreground/80",
  sage: "bg-[color-mix(in_oklab,var(--sage)_30%,white)] text-foreground",
  mist: "bg-[color-mix(in_oklab,var(--mist)_30%,white)] text-foreground",
  peach: "bg-[color-mix(in_oklab,var(--peach)_30%,white)] text-foreground",
};

interface ChipProps {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
}

export function Chip({ tone = "default", icon, children }: ChipProps) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium " +
        TONE_CLASS[tone]
      }
    >
      {icon}
      {children}
    </span>
  );
}
