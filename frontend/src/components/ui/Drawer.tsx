import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

/** Side panel (modal dialog). Controlled with open/onOpenChange, or opened by `trigger`. */
export function Drawer({
  title,
  description,
  trigger,
  open,
  onOpenChange,
  children,
}: {
  title: string;
  description?: string;
  trigger?: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>}
      <Dialog.Portal>
        <Dialog.Overlay className="shell-overlay" />
        <Dialog.Content className="ui-drawer">
          <div className="ui-drawer-head">
            <Dialog.Title className="ui-drawer-title">{title}</Dialog.Title>
            <Dialog.Close className="icon-btn" aria-label={`Close ${title}`}>
              <X size={18} aria-hidden="true" />
            </Dialog.Close>
          </div>
          {description ? (
            <Dialog.Description className="ui-drawer-desc">{description}</Dialog.Description>
          ) : (
            <Dialog.Description className="sr-only">{title}</Dialog.Description>
          )}
          <div className="ui-drawer-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
