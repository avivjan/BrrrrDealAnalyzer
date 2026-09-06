/** Types for `build-looks.mjs`. */
import type { LookData, LookPalette } from './looks.data.mjs';

export const LOOKS_DIR_URL: URL;
export const COLOR_TOKENS: [string, keyof LookPalette][];
export const CHART_NAMES: string[];
export const TOKEN_NAMES: string[];
export function hexToRgb(hex: string): [number, number, number];
export function mix(a: string, b: string, t: number): string;
export function chartLiterals(palette: LookPalette, mode: 'light' | 'dark'): Record<string, string>;
export function declarations(look: LookData, mode: 'light' | 'dark'): [string, string][];
export function renderLook(look: LookData): string;
export function build(options?: { check?: boolean; dirUrl?: URL }): string[];
