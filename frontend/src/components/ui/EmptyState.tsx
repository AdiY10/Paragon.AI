import type { ReactNode } from "react";
import { Compass } from "lucide-react";

/** Says what to do next; never shows numbers. */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <Compass size={24} aria-hidden="true" />
      <p className="empty-title">{title}</p>
      {children && <p className="empty-body">{children}</p>}
      {action}
    </div>
  );
}
