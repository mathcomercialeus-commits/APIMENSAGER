import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  tone?: "teal" | "amber" | "slate" | "crimson";
  helper?: string;
  icon?: ReactNode;
}

export function StatCard({ label, value, tone = "slate", helper, icon }: StatCardProps) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      <div className="stat-card__top">
        <strong>{label}</strong>
        {icon ? <span>{icon}</span> : null}
      </div>
      <div className="stat-card__value">{value}</div>
      {helper ? <p>{helper}</p> : null}
    </article>
  );
}
