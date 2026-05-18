"use client";

import { useState } from "react";
import { MapView } from "@/components/MapView";
import { Greeting } from "@/components/Greeting";
import { BottomSheet } from "@/components/BottomSheet";
import { InvitationCard } from "@/components/InvitationCard";
import { Chip } from "@/components/Chip";
import { demoEvents } from "@/lib/demoEvents";

export default function ResidentMapPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const selected = demoEvents.find((e) => e.id === selectedId) ?? null;

  function handleSelect(id: string) {
    setSelectedId(id);
    setSheetOpen(true);
  }

  return (
    <div className="relative h-[calc(100dvh-3.5rem)] w-full">
      {/* Map fills, right aside on desktop */}
      <div className="absolute inset-0 lg:right-[440px]">
        <MapView
          events={demoEvents}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      </div>

      {/* Floating greeting */}
      <div className="pointer-events-none absolute left-1/2 top-4 z-10 w-full max-w-md -translate-x-1/2 px-4">
        <div className="pointer-events-auto space-y-2">
          <Greeting invitationCount={demoEvents.length} />
          <Chip tone="sage">Small groups · Hosted · No pressure</Chip>
        </div>
      </div>

      {/* Desktop right aside */}
      <aside className="absolute right-0 top-0 hidden h-full w-[440px] flex-col overflow-y-auto border-l border-border bg-card p-6 lg:flex">
        {selected ? (
          <InvitationCard event={selected} />
        ) : (
          <div className="m-auto max-w-xs text-center">
            <p className="text-base font-medium">A few gentle options nearby</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Tap a pin on the map to see a calm invitation. Not this time is
              always okay.
            </p>
          </div>
        )}
      </aside>

      {/* Mobile bottom sheet */}
      <div className="lg:hidden">
        <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)}>
          {selected && <InvitationCard event={selected} />}
        </BottomSheet>
      </div>
    </div>
  );
}
