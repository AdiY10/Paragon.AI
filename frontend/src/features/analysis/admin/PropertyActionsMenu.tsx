import { useRef, useState } from "react";
import { ChevronDown, Compass, FileText, MapPin, Settings2 } from "lucide-react";
import { EditLocation } from "../../../components/LocationForms";
import { MenuButton } from "../../../components/ui/MenuButton";
import type { Location } from "../../../types";
import GeocodeDialog from "./GeocodeDialog";
import PinEditor from "./PinEditor";
import { RecordDrawer } from "./RecordDrawer";

type Dialog = "edit" | "pin" | "geocode" | "record" | null;

/** Admin-only "Property actions": each item opens a dialog; closing it returns focus to this button. */
export function PropertyActionsMenu({ location }: { location: Location }) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const button = useRef<HTMLButtonElement | null>(null);
  const returnFocus = () => requestAnimationFrame(() => button.current?.focus());
  const control = (name: Exclude<Dialog, null>) => ({
    open: dialog === name,
    onOpenChange: (open: boolean) => setDialog(open ? name : null),
    returnFocus,
  });
  const items: { name: Exclude<Dialog, null>; label: string; Icon: typeof MapPin }[] = [
    { name: "edit", label: "Edit details", Icon: Settings2 },
    { name: "pin", label: location.current_revision.lat === null ? "Place pin" : "Correct pin", Icon: MapPin },
    { name: "geocode", label: "Find address pin", Icon: Compass },
    { name: "record", label: "Record & history", Icon: FileText },
  ];
  return (
    <>
      <MenuButton
        label="Property actions"
        className="btn btn-secondary btn-sm"
        buttonRef={button}
        buttonContent={
          <>
            Property actions <ChevronDown size={14} aria-hidden="true" />
          </>
        }
      >
        {(close) => (
          <ul className="menu-list">
            {items.map(({ name, label, Icon }) => (
              <li key={name}>
                <button
                  type="button"
                  className="menu-item"
                  onClick={() => {
                    close();
                    setDialog(name);
                  }}
                >
                  <Icon size={16} aria-hidden="true" />
                  {label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </MenuButton>
      <EditLocation location={location} {...control("edit")} />
      <PinEditor location={location} {...control("pin")} />
      <GeocodeDialog location={location} {...control("geocode")} />
      <RecordDrawer location={location} {...control("record")} />
    </>
  );
}
