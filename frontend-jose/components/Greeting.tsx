"use client";

function timeOfDayGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

interface GreetingProps {
  invitationCount: number;
  name?: string;
}

export function Greeting({ invitationCount, name = "Sofia" }: GreetingProps) {
  return (
    <div className="rounded-3xl border border-border bg-card/95 px-5 py-4 shadow-[var(--shadow-float)] backdrop-blur">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {timeOfDayGreeting()}
      </p>
      <p className="mt-1 text-[15px] font-medium leading-tight">
        Hi {name}.
      </p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        {invitationCount > 0
          ? `You have ${invitationCount} gentle ${invitationCount === 1 ? "invitation" : "invitations"} nearby.`
          : "No invitations right now."}
        <br />
        No rush today.
      </p>
    </div>
  );
}
