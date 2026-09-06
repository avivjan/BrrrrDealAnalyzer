/**
 * Focus containment for a modal overlay, the cheap way: while `root` is open,
 * every other direct child of `<body>` is `inert`, so Tab cannot walk behind
 * the scrim and assistive tech treats the rest of the page as unavailable —
 * which is what `aria-modal="true"` already claims. Siblings that are themselves
 * open overlays (`data-overlay`) are left alone, so a palette can sit over a
 * drawer. `inert` is supported from iOS/Safari 15.5 and degrades to today's
 * behaviour below that.
 *
 * Returns the release function; call it on close and on unmount.
 */
export function inertOutside(root: HTMLElement): () => void {
  if (typeof document === "undefined") return () => undefined;
  const made: Element[] = [];
  for (const child of Array.from(document.body.children)) {
    if (child === root || child.contains(root)) continue;
    if (child.hasAttribute("data-overlay")) continue;
    if (child.hasAttribute("inert")) continue;
    if (child.tagName === "SCRIPT" || child.tagName === "STYLE") continue;
    child.setAttribute("inert", "");
    made.push(child);
  }
  return () => {
    for (const el of made) el.removeAttribute("inert");
  };
}
