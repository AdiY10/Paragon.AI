import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * Disclosure-pattern menu: a button with aria-expanded that shows a panel of ordinary links and
 * buttons. Escape closes and returns focus to the button; clicking or tabbing outside closes it.
 */
export function MenuButton({
  label,
  buttonContent,
  className = "nav-button",
  children,
}: {
  /** Accessible name of the button, e.g. "Account menu". */
  label: string;
  buttonContent: ReactNode;
  className?: string;
  /** Panel content; call close() after an item acts. */
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div
      className="menu"
      ref={root}
      onBlur={(event) => {
        if (open && event.relatedTarget && !root.current?.contains(event.relatedTarget as Node)) setOpen(false);
      }}
    >
      <button
        ref={button}
        type="button"
        className={className}
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {buttonContent}
      </button>
      <div className="menu-panel" id={panelId} hidden={!open}>
        {children(() => setOpen(false))}
      </div>
    </div>
  );
}
