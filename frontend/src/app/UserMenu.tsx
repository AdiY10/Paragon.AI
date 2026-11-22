import { ChevronDown, Database, LogOut, Settings2 } from "lucide-react";
import { MenuButton } from "../components/ui/MenuButton";
import { csrfToken } from "../api/client";
import type { Session } from "../types";
import { accountLinks } from "./nav";

const roleLabel = (role: Session["role"]) => (role === "admin" ? "Administrator" : "Member");

/** Sign-out is a POST with the CSRF token (Django's logout view refuses GET). */
export function SignOutForm({ session, className = "menu-item" }: { session: Session; className?: string }) {
  return (
    <form action={session.logout_url ?? "/accounts/logout/"} method="post">
      <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken()} />
      <button className={className} type="submit">
        <LogOut size={16} aria-hidden="true" />
        Sign out
      </button>
    </form>
  );
}

export function UserMenu({ session }: { session: Session }) {
  return (
    <MenuButton
      label="Account menu"
      className="nav-button account-trigger"
      buttonContent={
        <>
          <span className="avatar" aria-hidden="true">
            {session.email.slice(0, 1).toUpperCase()}
          </span>
          <ChevronDown size={14} aria-hidden="true" />
        </>
      }
    >
      {(close) => (
        <>
          <div className="menu-header">
            <strong>{session.email}</strong>
            <small>{roleLabel(session.role)}</small>
          </div>
          <ul className="menu-list">
            {accountLinks(session).map((item) => (
              <li key={item.to}>
                <a className="menu-item" href={"#" + item.to} onClick={close}>
                  {item.to === "/admin" ? (
                    <Settings2 size={16} aria-hidden="true" />
                  ) : (
                    <Database size={16} aria-hidden="true" />
                  )}
                  {item.label}
                </a>
              </li>
            ))}
            <li>
              <SignOutForm session={session} />
            </li>
          </ul>
        </>
      )}
    </MenuButton>
  );
}
