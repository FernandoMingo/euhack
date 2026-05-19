"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Leaf, Map, ShieldCheck, Stethoscope } from "lucide-react";

const TABS = [
  { href: "/", label: "Resident", icon: Map },
  { href: "/professional", label: "Professional", icon: Stethoscope },
  { href: "/operator", label: "Operator", icon: ShieldCheck },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-[100dvh] flex flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-card/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium tracking-wide"
          >
            <span
              className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-[color-mix(in_oklab,var(--sage)_30%,white)]"
              aria-hidden
            >
              <Leaf size={16} strokeWidth={1.8} />
            </span>
            CivicCircles
          </Link>
          <nav className="flex items-center gap-1 rounded-full border border-border bg-card/60 p-1 text-xs sm:text-sm">
            {TABS.map(({ href, label, icon: Icon }) => {
              const active =
                href === "/" ? pathname === "/" : pathname?.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={
                    "flex items-center gap-2 rounded-full px-3 py-1.5 transition-colors " +
                    (active
                      ? "bg-[color-mix(in_oklab,var(--sage)_45%,white)] text-foreground"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  <Icon size={14} strokeWidth={1.8} />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
