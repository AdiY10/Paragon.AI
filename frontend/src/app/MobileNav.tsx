import { useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import type { Session } from "../types";
import { accountLinks, MAIN_NAV } from "./nav";
import { isActive } from "./router";
import { SignOutForm } from "./UserMenu";

/** ≤640 px: the top navigation moves into a modal dialog (focus trapped, returned on close). */
export function MobileNav({ session, path }: { session: Session; path: string }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button ref={trigger} type="button" className="nav-button icon-only menu-toggle" aria-label="Open navigation">
          <Menu size={18} aria-hidden="true" />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="shell-overlay" />
        <Dialog.Content
          className="mobile-nav"
          onCloseAutoFocus={(event) => {
            // Return focus after the dialog's layers are gone; Radix's own return can land on <body>
            // when Escape closes it.
            event.preventDefault();
            requestAnimationFrame(() => trigger.current?.focus());
          }}
        >
          <div className="mobile-nav-head">
            <span className="brand" aria-hidden="true">
              <span className="brand-mark">P</span>
              <span>
                PARAGON <span className="brand-sub">RADAR</span>
              </span>
            </span>
            <Dialog.Title className="sr-only">Workspace navigation</Dialog.Title>
            <Dialog.Close className="icon-btn" aria-label="Close navigation">
              <X size={18} aria-hidden="true" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Choose a page or sign out.</Dialog.Description>
          <nav aria-label="Pages">
            <ul>
              {MAIN_NAV.map((item) => (
                <li key={item.to}>
                  <a
                    href={"#" + item.to}
                    aria-current={isActive(item.to, path) ? "page" : undefined}
                    onClick={close}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <hr />
          <div className="menu-header">
            <strong>{session.email}</strong>
          </div>
          <ul>
            {accountLinks(session).map((item) => (
              <li key={item.to}>
                <a href={"#" + item.to} aria-current={isActive(item.to, path) ? "page" : undefined} onClick={close}>
                  {item.label}
                </a>
              </li>
            ))}
            <li>
              <SignOutForm session={session} />
            </li>
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
