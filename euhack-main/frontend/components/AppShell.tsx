import Link from "next/link";
import type { ReactNode } from "react";
import { Camera, ClipboardList, Map, ShieldCheck } from "lucide-react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="fixed left-0 right-0 top-0 z-40 border-b border-line/20 bg-paper/88 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-wide text-ink">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line/30 bg-oat/70">
              <Camera size={18} strokeWidth={1.7} />
            </span>
            CivicCircles
          </Link>
          <nav className="flex items-center gap-1 rounded-lg border border-line/20 bg-white/35 p-1 text-sm">
            <Link className="tap-target flex items-center gap-2 rounded-md px-3 text-ink/80 hover:bg-white/60" href="/">
              <Map size={16} strokeWidth={1.7} />
              Map
            </Link>
            <Link className="tap-target flex items-center gap-2 rounded-md px-3 text-ink/80 hover:bg-white/60" href="/professional">
              <ClipboardList size={16} strokeWidth={1.7} />
              Professional
            </Link>
            <Link className="tap-target flex items-center gap-2 rounded-md px-3 text-ink/80 hover:bg-white/60" href="/operator">
              <ShieldCheck size={16} strokeWidth={1.7} />
              Operator
            </Link>
          </nav>
        </div>
      </header>
      <main className="pt-16">{children}</main>
    </div>
  );
}
