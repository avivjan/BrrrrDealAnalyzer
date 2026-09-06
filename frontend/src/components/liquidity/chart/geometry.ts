/**
 * Pure geometry for the liquidity timeline: where a day sits, where a balance
 * sits, which days are on screen, and where the keyboard goes next. No DOM,
 * no colours — `TimelineChart.vue` owns those. Everything here is unit-tested
 * in `geometry.test.ts`.
 */

/** Horizontal room per day, in CSS px. */
export const DAY_WIDTH = 48;
export const PAD_TOP = 40;
export const PAD_BOTTOM = 52;
export const PAD_LEFT = 72;
export const PAD_RIGHT = 24;

export interface Range {
  min: number;
  max: number;
}

/** Vertical range with 12% breathing room; the floor is pulled down to zero when the series is positive. */
export function balanceRange(balances: readonly number[]): Range {
  if (balances.length === 0) return { min: 0, max: 100 };
  let min = Infinity;
  let max = -Infinity;
  for (const b of balances) {
    if (b < min) min = b;
    if (b > max) max = b;
  }
  const pad = Math.max((max - min) * 0.12, 5);
  return { min: Math.min(min - pad, 0), max: max + pad };
}

export function totalWidth(count: number): number {
  return count * DAY_WIDTH + PAD_LEFT + PAD_RIGHT;
}

/** Centre x of day `i` given the current horizontal scroll. */
export function xForIndex(i: number, scrollX: number): number {
  return PAD_LEFT + i * DAY_WIDTH + DAY_WIDTH / 2 - scrollX;
}

/** Day under an x position measured from the container's left edge, or null. */
export function indexForOffsetX(offsetX: number, scrollX: number, count: number): number | null {
  // The y-axis gutter is not a day.
  if (offsetX < PAD_LEFT) return null;
  const x = offsetX + scrollX - PAD_LEFT;
  const idx = Math.floor(x / DAY_WIDTH);
  return idx < 0 || idx >= count ? null : idx;
}

export function yForBalance(balance: number, height: number, range: Range): number {
  const span = range.max - range.min || 1;
  const plotH = height - PAD_TOP - PAD_BOTTOM;
  return PAD_TOP + plotH * (1 - (balance - range.min) / span);
}

export function clampScroll(scrollX: number, count: number, viewWidth: number): number {
  const maxScroll = Math.max(0, totalWidth(count) - viewWidth);
  return Math.max(0, Math.min(scrollX, maxScroll));
}

/** Scroll that puts day `idx` about a third of the way into the view. */
export function scrollToCentre(idx: number, viewWidth: number, count: number): number {
  return clampScroll(PAD_LEFT + idx * DAY_WIDTH - viewWidth * 0.37, count, viewWidth);
}

/** The scroll that keeps `idx` on screen, moving only when it would leave. */
export function scrollToReveal(idx: number, scrollX: number, viewWidth: number, count: number): number {
  const x = PAD_LEFT + idx * DAY_WIDTH;
  let next = scrollX;
  if (x - scrollX < PAD_LEFT + 20) next = x - PAD_LEFT - 40;
  else if (x - scrollX > viewWidth - DAY_WIDTH) next = x - viewWidth + DAY_WIDTH + 12;
  return clampScroll(next, count, viewWidth);
}

/** `[first, last]` inclusive indices worth rendering, with a two-day margin. */
export function visibleRange(scrollX: number, viewWidth: number, count: number): [number, number] {
  if (count === 0) return [0, -1];
  const first = Math.max(0, Math.floor((scrollX - PAD_LEFT) / DAY_WIDTH) - 1);
  const last = Math.min(count - 1, first + Math.ceil(viewWidth / DAY_WIDTH) + 3);
  return [first, last];
}

/**
 * Keyboard contract: with nothing selected either arrow lands on 0; otherwise
 * arrows move one step and clamp. `null` means "no move" (unknown key, or an
 * empty series).
 */
export function nextIndex(current: number | null, key: string, count: number): number | null {
  if (count === 0) return null;
  if (key !== "ArrowRight" && key !== "ArrowLeft") return null;
  if (current === null) return 0;
  return key === "ArrowRight" ? Math.min(current + 1, count - 1) : Math.max(current - 1, 0);
}

/** "Nice" tick values between min and max, about `target` of them. */
export function niceGridSteps(min: number, max: number, target: number): number[] {
  const range = max - min;
  if (range <= 0) return [0];
  const rough = range / target;
  const mag = 10 ** Math.floor(Math.log10(rough));
  let step = mag;
  if (rough / mag >= 5) step = mag * 5;
  else if (rough / mag >= 2) step = mag * 2;
  const steps: number[] = [];
  let v = Math.ceil(min / step) * step;
  while (v <= max) {
    steps.push(Math.round(v * 1000) / 1000);
    v += step;
  }
  return steps;
}

export function formatK(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}M`;
  return `${value.toFixed(1)}k`;
}

export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function parseDateParts(iso: string): [string, string, string] {
  const parts = iso.split("-");
  return [parts[0] ?? "", parts[1] ?? "", parts[2] ?? ""];
}

export function weekday(iso: string): number {
  return new Date(`${iso}T00:00:00`).getDay();
}

export function formatDateLong(iso: string): string {
  const [, mo, dy] = parseDateParts(iso);
  return `${WEEKDAY_NAMES[weekday(iso)] ?? ""}, ${MONTH_NAMES[parseInt(mo, 10) - 1] ?? ""} ${parseInt(dy, 10)}`;
}

// ---------------------------------------------------------------------------
// line + area (UI v3: the balance is one line with a filled area, no bars)
// ---------------------------------------------------------------------------

export interface Point {
  x: number;
  y: number;
}

/** A point that still knows the balance it was plotted from. */
export interface Sample extends Point {
  value: number;
}

/** One same-sign stretch of the series, with the sample indices it spans (inclusive). */
export interface Run {
  positive: boolean;
  points: Point[];
  first: number;
  last: number;
}

const fmt = (n: number) => n.toFixed(1);

/** `M x,y L x,y …` through the points; `''` for none. */
export function linePath(points: readonly Point[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${fmt(p.x)},${fmt(p.y)}`).join(" ");
}

/** The line, closed straight down to `baseY` and back along it; `''` for none. */
export function areaPath(points: readonly Point[], baseY: number): string {
  if (points.length === 0) return "";
  const first = points[0]!;
  const last = points[points.length - 1]!;
  return `${linePath(points)} L${fmt(last.x)},${fmt(baseY)} L${fmt(first.x)},${fmt(baseY)} Z`;
}

/**
 * Split a polyline into runs of one sign (zero counts as positive). Where the
 * sign flips between two samples the interpolated crossing point ends one run
 * and starts the next, so their areas meet exactly on the zero line.
 */
export function splitAtZero(samples: readonly Sample[]): Run[] {
  const runs: Run[] = [];
  let run: Run | null = null;
  for (let i = 0; i < samples.length; i += 1) {
    const s = samples[i]!;
    const positive = s.value >= 0;
    if (run && run.positive !== positive) {
      const a = samples[i - 1]!;
      const t = a.value / (a.value - s.value);
      const cross = { x: a.x + (s.x - a.x) * t, y: a.y + (s.y - a.y) * t };
      run.points.push(cross);
      run = { positive, points: [cross], first: i, last: i };
      runs.push(run);
    } else if (!run) {
      run = { positive, points: [], first: i, last: i };
      runs.push(run);
    }
    run.points.push({ x: s.x, y: s.y });
    run.last = i;
  }
  return runs;
}
