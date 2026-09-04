/**
 * Compose Tailwind class names.
 *
 * `clsx` flattens whatever shape the caller finds convenient — strings,
 * arrays, `{ 'is-open': open }` objects — into one list; `twMerge` then throws
 * away every utility that a later one overrides. That second step is the
 * reason this exists: `class="bg-surface" + class="bg-primary"` is otherwise
 * two live rules whose winner is decided by stylesheet order, not by the
 * caller's intent, so a component prop meant to override a default silently
 * does nothing on some builds and works on others.
 */
import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge with this project's scales taught to it.
 *
 * It reads colour utilities structurally, so `bg-primary` and `text-fg-muted`
 * already merge against `bg-gray-50` and friends with no configuration. The
 * four scales below are different: they are enumerated key lists, and a bare
 * `rounded-card` is indistinguishable from a class tailwind-merge has never
 * heard of — so without this, `cn('rounded-lg', 'rounded-card')` would keep
 * *both* and hand the decision back to stylesheet order, which is exactly the
 * bug `cn` exists to prevent.
 *
 * The keys mirror `tailwind.config.js`, which mirrors `src/assets/tokens.css`.
 * Adding a key in one place means adding it here.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      // `--radius-sm/md/lg`; Tailwind's own `rounded-sm/md/lg` are untouched.
      rounded: [{ rounded: ["ctl", "card", "panel"] }],
      // `--shadow-1/2/3`. This is the elevation group, not `shadow-color`:
      // `shadow-2 shadow-primary` is a tinted elevation and must survive.
      shadow: [{ shadow: ["1", "2", "3"] }],
      // `--dur-fast/base/slow`.
      duration: [{ duration: ["fast", "base", "slow"] }],
      // `--ease-standard/emphasized/exit`.
      ease: [{ ease: ["standard", "emphasized", "exit"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
