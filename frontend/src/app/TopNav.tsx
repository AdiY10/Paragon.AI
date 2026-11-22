import type { Session } from "../types";
import { GlobalSearch } from "./GlobalSearch";
import { MobileNav } from "./MobileNav";
import { MAIN_NAV } from "./nav";
import { isActive } from "./router";
import { UserMenu } from "./UserMenu";

export function TopNav({ session, path }: { session: Session; path: string }) {
  return (
    <header className="topnav">
      <div className="topnav-inner">
        <MobileNav session={session} path={path} />
        <a className="brand" href="#/" aria-label="Paragon Radar home">
          <span className="brand-mark" aria-hidden="true">
            P
          </span>
          <span aria-hidden="true">
            PARAGON <span className="brand-sub">RADAR</span>
          </span>
        </a>
        <nav className="main-nav" aria-label="Main">
          <ul>
            {MAIN_NAV.map((item) => (
              <li key={item.to}>
                <a href={"#" + item.to} aria-current={isActive(item.to, path) ? "page" : undefined}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="topnav-actions">
          <GlobalSearch />
          <UserMenu session={session} />
        </div>
      </div>
    </header>
  );
}
