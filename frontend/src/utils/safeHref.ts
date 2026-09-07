/**
 * A user- or API-supplied URL that is safe to bind to `:href`.
 *
 * Vue does not sanitise `:href`, so a deal's `zillow_link`, a comp URL or an
 * evidence link of `javascript:...` would run on click with this origin's
 * storage in reach. Only `http:` and `https:` are ever meant here; anything
 * else (`javascript:`, `data:`, a bare host, an empty field) yields
 * `undefined`, which renders the anchor without an `href` -- the same dead
 * link a scheme-less value already was.
 */
export function safeHref(value: string | null | undefined): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : undefined;
}
