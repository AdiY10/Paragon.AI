import { useId, type ReactNode } from "react";

/** A bordered panel. With a title it becomes a labelled region (h2 by default). */
export function Card({
  title,
  level = 2,
  actions,
  footer,
  className = "",
  children,
}: {
  title?: ReactNode;
  level?: 2 | 3;
  actions?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section className={`card ${className}`.trim()} aria-labelledby={title ? id : undefined}>
      {(title || actions) && (
        <div className="card-head">
          {title && (
            <Heading id={id} className="card-title">
              {title}
            </Heading>
          )}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
      {footer && <div className="card-footer">{footer}</div>}
    </section>
  );
}
