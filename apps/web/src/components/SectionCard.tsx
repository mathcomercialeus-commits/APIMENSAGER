import type { ReactNode } from "react";

interface SectionCardProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function SectionCard({ title, description, actions, children }: SectionCardProps) {
  return (
    <section className="section-card">
      <header className="section-card__header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="section-card__actions">{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}
