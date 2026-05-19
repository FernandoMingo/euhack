"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Archive,
  CalendarDays,
  Inbox as InboxIcon,
  MailOpen,
  MapPin,
  Sparkles,
} from "lucide-react";
import { Chip } from "@/components/Chip";
import {
  ApiError,
  api,
  readDemoSession,
  type ResidentInboxItem,
} from "@/lib/api";

export default function ResidentInboxPage() {
  const router = useRouter();
  const [residentId, setResidentId] = useState<string | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [items, setItems] = useState<ResidentInboxItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const session = readDemoSession();
    setResidentId(session.resident_id ?? null);
    setSessionChecked(true);
    if (!session.resident_id) {
      router.replace("/login");
    }
  }, [router]);

  const load = useCallback(
    async (rid: string) => {
      setError(null);
      try {
        const data = await api.residentInboxItems(rid);
        setItems(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [router]
  );

  useEffect(() => {
    if (!residentId) return;
    load(residentId);
  }, [residentId, load]);

  async function markRead(item: ResidentInboxItem) {
    if (!residentId || item.status !== "unread") return;
    setBusy("read:" + item.id);
    try {
      const updated = await api.markInboxItemRead(residentId, item.id);
      setItems((prev) =>
        prev.map((it) => (it.id === updated.id ? updated : it))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function archive(item: ResidentInboxItem) {
    if (!residentId) return;
    setBusy("archive:" + item.id);
    try {
      const updated = await api.archiveInboxItem(residentId, item.id);
      setItems((prev) =>
        prev.map((it) => (it.id === updated.id ? updated : it))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  if (!sessionChecked) return null;
  if (!residentId) return null;

  const visible = items.filter((it) => it.status !== "archived");
  const unreadCount = visible.filter((it) => it.status === "unread").length;

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-4 py-8 sm:px-6">
      <header className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Your inbox
        </p>
        <h1 className="text-[26px] font-medium leading-tight">
          Invitations from CivicCircles
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          The same calm invitations you receive by email. Open one to see
          where, when, and how to say yes.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Chip tone="sage" icon={<InboxIcon size={12} strokeWidth={1.8} />}>
          {visible.length} item{visible.length === 1 ? "" : "s"}
        </Chip>
        {unreadCount > 0 && (
          <Chip tone="mist">{unreadCount} unread</Chip>
        )}
      </div>

      {error && (
        <div className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {visible.length === 0 && !error && (
        <section className="rounded-3xl border border-border bg-card p-8 text-center shadow-[var(--shadow-soft)]">
          <Sparkles
            size={28}
            strokeWidth={1.6}
            className="mx-auto text-muted-foreground"
          />
          <p className="mt-3 text-sm font-medium">No invitations yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            When an operator approves a calm circle for you, it will appear
            here and in your email.
          </p>
        </section>
      )}

      <ul className="space-y-3">
        {visible.map((item) => (
          <InboxRow
            key={item.id}
            item={item}
            busy={busy}
            onRead={() => markRead(item)}
            onArchive={() => archive(item)}
          />
        ))}
      </ul>
    </div>
  );
}

function InboxRow({
  item,
  busy,
  onRead,
  onArchive,
}: {
  item: ResidentInboxItem;
  busy: string | null;
  onRead: () => void;
  onArchive: () => void;
}) {
  const unread = item.status === "unread";
  const startAt = item.metadata?.activity_start_at;
  const when = startAt ? new Date(startAt) : null;
  const dateLabel = when
    ? when.toLocaleDateString(undefined, {
        weekday: "long",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : null;
  const venueLabel = item.metadata?.venue_name
    ? `${item.metadata.venue_name}${
        item.metadata.venue_city ? " · " + item.metadata.venue_city : ""
      }`
    : null;

  return (
    <li
      className={
        "rounded-3xl border p-5 shadow-[var(--shadow-soft)] transition-colors " +
        (unread
          ? "border-[color-mix(in_oklab,var(--sage)_45%,var(--border))] bg-[color-mix(in_oklab,var(--sage)_8%,var(--card))]"
          : "border-border bg-card")
      }
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{item.title}</span>
            {unread && <Chip tone="sage">New</Chip>}
          </div>
          <p className="text-sm text-muted-foreground whitespace-pre-line">
            {item.body}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {unread && (
            <button
              type="button"
              onClick={onRead}
              disabled={busy === "read:" + item.id}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-60"
            >
              <MailOpen size={12} strokeWidth={1.8} />
              Mark read
            </button>
          )}
          <button
            type="button"
            onClick={onArchive}
            disabled={busy === "archive:" + item.id}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-60"
          >
            <Archive size={12} strokeWidth={1.8} />
            Archive
          </button>
        </div>
      </header>

      {(dateLabel || venueLabel) && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {dateLabel && (
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays size={12} strokeWidth={1.8} />
              {dateLabel}
            </span>
          )}
          {venueLabel && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={12} strokeWidth={1.8} />
              {venueLabel}
            </span>
          )}
        </div>
      )}

      {item.activity_id && (
        <div className="mt-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-2 text-xs font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
          >
            See it on the map
          </Link>
        </div>
      )}
    </li>
  );
}
