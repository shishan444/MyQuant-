import { type ReactNode, useCallback, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";

interface DropdownPortalProps {
  triggerRef: React.RefObject<HTMLElement | null>;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: number | string;
}

export function DropdownPortal({
  triggerRef,
  open,
  onClose,
  children,
  width,
}: DropdownPortalProps) {
  const [pos, setPos] = useState({ top: 0, left: 0, w: 0 as number | string });

  const update = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({
      top: rect.bottom + 4,
      left: rect.left,
      w: width ?? rect.width,
    });
  }, [triggerRef, width]);

  useLayoutEffect(() => {
    if (!open) return;
    update();
  }, [open, update]);

  useLayoutEffect(() => {
    if (!open) return;
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, update]);

  if (!open) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        style={{ position: "fixed", inset: 0, zIndex: 9998 }}
        onClick={onClose}
      />
      {/* Dropdown panel */}
      <div
        style={{
          position: "fixed",
          top: pos.top,
          left: pos.left,
          width: pos.w,
          zIndex: 9999,
        }}
      >
        {children}
      </div>
    </>,
    document.body,
  );
}
