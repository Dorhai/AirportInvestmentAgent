import {
  useCallback,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface MetricLabelHintProps {
  label: string;
  description: string;
  className?: string;
  align?: "start" | "center" | "end";
  /** Dotted underline cues that a definition is available (off for compact badges). */
  underline?: boolean;
  /** Tooltip placement relative to the label (below avoids clipping in scrollable tables). */
  side?: "top" | "bottom";
}

function tooltipTransform(
  align: "start" | "center" | "end",
  side: "top" | "bottom",
): string | undefined {
  const y = side === "top" ? "translateY(-100%)" : "";
  if (align === "center") {
    return side === "top" ? "translate(-50%, -100%)" : "translateX(-50%)";
  }
  if (align === "end") {
    return side === "top" ? "translate(-100%, -100%)" : "translateX(-100%)";
  }
  return y || undefined;
}

export function MetricLabelHint({
  label,
  description,
  className,
  align = "center",
  underline = true,
  side = "bottom",
}: MetricLabelHintProps) {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState<CSSProperties | null>(null);

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const gap = 6;
    const maxWidth = Math.min(320, window.innerWidth - 16);

    const top =
      side === "bottom" ? rect.bottom + gap : rect.top - gap;
    let left = rect.left;
    if (align === "center") {
      left = rect.left + rect.width / 2;
    } else if (align === "end") {
      left = rect.right;
    }

    setStyle({
      position: "fixed",
      top,
      left,
      maxWidth,
      zIndex: 9999,
      transform: tooltipTransform(align, side),
    });
  }, [align, side]);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    const onScrollOrResize = () => updatePosition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open, updatePosition]);

  const show = () => {
    setOpen(true);
    requestAnimationFrame(updatePosition);
  };
  const hide = () => setOpen(false);

  const tooltip =
    open &&
    style &&
    createPortal(
      <span
        id={tooltipId}
        role="tooltip"
        style={style}
        className={cn(
          "pointer-events-none border border-ink bg-white px-2 py-1",
          "text-left text-[10px] font-normal normal-case leading-tight tracking-normal text-ink shadow-md",
        )}
      >
        {description}
      </span>,
      document.body,
    );

  return (
    <>
      <span
        ref={triggerRef}
        tabIndex={0}
        aria-label={`${label}. ${description}`}
        aria-describedby={open ? tooltipId : undefined}
        className={cn(
          "inline-block max-w-full cursor-help",
          underline &&
            "border-b border-dotted border-ink-muted/40 hover:border-ink-muted hover:text-ink",
          "focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-ink",
          className,
        )}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        {label}
      </span>
      {tooltip}
    </>
  );
}
