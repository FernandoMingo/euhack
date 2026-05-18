"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { X } from "lucide-react";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function BottomSheet({ open, onClose, children }: BottomSheetProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={
          "fixed inset-0 z-40 bg-foreground/10 backdrop-blur-[2px] transition-opacity duration-200 " +
          (open ? "opacity-100" : "pointer-events-none opacity-0")
        }
        aria-hidden
      />
      <div
        className={
          "fixed bottom-0 left-0 right-0 z-50 mx-auto w-full max-w-2xl rounded-t-[28px] border border-border bg-card shadow-[var(--shadow-float)] transition-transform duration-300 lg:bottom-6 lg:right-6 lg:left-auto lg:w-[440px] lg:rounded-[28px] " +
          (open ? "translate-y-0" : "translate-y-full lg:translate-y-[110%]")
        }
        role="dialog"
        aria-modal="true"
      >
        <div className="mx-auto mt-3 h-1.5 w-10 rounded-full bg-border lg:hidden" />
        <button
          onClick={onClose}
          className="absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Close"
        >
          <X size={16} strokeWidth={1.8} />
        </button>
        <div className="max-h-[88vh] overflow-y-auto px-5 pb-6 pt-4 lg:max-h-[80vh]">
          {children}
        </div>
      </div>
    </>
  );
}
