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
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
