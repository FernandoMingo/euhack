"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Inbox,
  Leaf,
  LogOut,
  Map,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import {
  readDemoSession,
  resetDemoSession,
  type DemoSession,
} from "@/lib/api";

const RESIDENT_TABS = [
  { href: "/", label: "Map", icon: Map },
  { href: "/inbox", label: "Inbox", icon: Inbox },
] as const;

const STAFF_TABS = [
  { href: "/staff/professional", label: "Professional", icon: Stethoscope },
  { href: "/staff/operator", label: "Operator", icon: ShieldCheck },
] as const;

function isStaffPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return pathname.startsWith("/staff");
}

function isAuthPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return pathname === "/login";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<DemoSession>({});

  useEffect(() => {
    setSession(readDemoSession());
  }, [pathname]);

  const staffMode = isStaffPath(pathname);
  const onLoginPage = isAuthPath(pathname);
  const TABS = staffMode ? STAFF_TABS : RESIDENT_TABS;

  function handleLogout() {
    resetDemoSession();
    setSession({});
    router.push("/login");
  }

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-card/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            href={staffMode ? "/staff/operator" : "/"}
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

          {!onLoginPage && (
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
          )}

          <div className="hidden items-center gap-2 sm:flex">
            {!staffMode && session.resident_id && (
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                title="Sign out"
              >
                <LogOut size={12} strokeWidth={1.8} />
                {session.resident_first_name ?? "Sign out"}
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
