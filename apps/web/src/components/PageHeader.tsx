import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
  meta?: ReactNode;
}

export function PageHeader({ title, description, actions, meta }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
        {meta ? <div className="page-header__meta">{meta}</div> : null}
      </div>
      {actions ? <div className="section-card__actions">{actions}</div> : null}
    </header>
  );
}
