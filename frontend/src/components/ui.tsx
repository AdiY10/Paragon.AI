import { type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Compass, X } from "lucide-react";
import { type Source } from "../types";

export function hashParams() {
  return new URLSearchParams(window.location.hash.split("?")[1] ?? "");
}
export const titleCase = (text: string) =>
  text.replaceAll("_", " ").replace(/\b\w/g, (s) => s.toUpperCase());
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function ErrorNotice({ error }: { error: unknown }) {
  return (
    <p className="notice error" role="alert">
      {error instanceof Error ? error.message : "Unable to load this section."}
    </p>
  );
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <Compass size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function PageHead({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Drawer({
  trigger,
  title,
  children,
}: {
  trigger: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="drawer">
          <div className="drawer-head">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Source, context, and supporting records.
          </Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
