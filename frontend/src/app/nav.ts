import type { Session } from "../types";

/** Top navigation (left to right). Properties stays active on property analyses. */
export const MAIN_NAV: { to: string; label: string }[] = [
  { to: "/", label: "Properties" },
  { to: "/analyze", label: "Analyze" },
  { to: "/alerts", label: "Alerts" },
  { to: "/compare", label: "Compare" },
];

/** Account menu destinations; Admin only for administrators. */
export function accountLinks(session: Session): { to: string; label: string }[] {
  return [
    { to: "/sources", label: "Data sources" },
    ...(session.role === "admin" ? [{ to: "/admin", label: "Admin" }] : []),
  ];
}

/** Hands a typed address from search to the Analyze page without putting it in the URL. */
let pendingAddress = "";
export function setPendingAddress(address: string) {
  pendingAddress = address;
}
export function takePendingAddress() {
  const value = pendingAddress;
  pendingAddress = "";
  return value;
}
