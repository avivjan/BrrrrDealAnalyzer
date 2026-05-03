// Type contracts for the REPS (Real Estate Professional Status) tracker.
// Mirrors `BackEnd/ReqRes/reps/repsReq.py` — keep in sync.

export type RepsUser = 'Aviv2026' | 'Yarden2026';

export const REPS_USERS: RepsUser[] = ['Aviv2026', 'Yarden2026'];

export const REPS_USER_DISPLAY: Record<RepsUser, string> = {
  Aviv2026: 'Aviv',
  Yarden2026: 'Yarden',
};

// Built-in fallback list shown if /reps/activity-categories isn't reachable
// (e.g. offline). Real categories come from the backend store.
export const FALLBACK_REPS_ACTIVITY_CATEGORIES = [
  'Acquisition / Underwriting',
  'Construction / Rehab Oversight',
  'Property Management',
  'Tenant / Leasing',
  'Bookkeeping / Admin',
  'Education / Research',
  'Travel — Property',
  'Refinance / Lender Calls',
  'Other',
] as const;

// Discrete moments at which the browser captures a GPS snapshot. Mirrors
// `LocationSnapshotKind` in `repsReq.py`.
export type LocationSnapshotKind =
  | 'manual_save'
  | 'timer_start'
  | 'timer_pause'
  | 'timer_resume'
  | 'timer_stop'
  | 'bookmark'
  | 'evidence_capture';

export interface LocationSnapshot {
  kind: LocationSnapshotKind;
  captured_at: string; // ISO 8601
  lat?: number | null;
  lng?: number | null;
  accuracy_m?: number | null;
  // Free-text override / context, e.g. "Remote", "permission_denied".
  note?: string | null;
}

export interface RepsActivityCategoryRes {
  id: string;
  name: string;
  sort_order?: number;
  is_default?: boolean;
}

export interface RepsUploadedFile {
  name: string;
  url: string;
  content_type?: string | null;
  size_bytes?: number;
}

export interface RepsUploadBatchRes {
  folder_url?: string | null;
  folder_path: string;
  files: RepsUploadedFile[];
}

export interface RepsLogPayload {
  user: RepsUser;
  property_name?: string | null;
  activity_category?: string | null;
  description: string;
  start_time: string; // ISO 8601 with timezone
  end_time: string;   // ISO 8601 with timezone
  // NEW: array of evidence URLs (uploaded via /reps/upload-batch first).
  evidence_links?: string[];
  evidence_folder?: string | null;
  // Legacy single-link, accepted for backward compat by the backend.
  evidence_link?: string | null;
  // NEW: device-GPS breadcrumbs across the session.
  location_snapshots?: LocationSnapshot[];
  // Legacy free-text fallback.
  location?: string | null;
  material_participation_rentals: boolean;
  people_involved: string[];
}

export interface RepsLogRes extends RepsLogPayload {
  created_at: string;
  total_hours: number;
  spreadsheet_id: string;
  appended_range: string;
}

export interface RepsEntryRow {
  created_at: string | null;
  user: string | null;
  property_name: string | null;
  activity_category: string | null;
  description: string | null;
  start_time: string | null;
  end_time: string | null;
  total_hours: number;
  evidence_link: string | null;
  location: string | null;
  material_participation_rentals: boolean;
  people_involved: string[];
}

export interface RepsStats {
  user: RepsUser;
  total_hours: number;
  material_hours: number;
  non_material_hours: number;
  entry_count: number;
  days_elapsed: number;
  days_in_year: number;
  year_progress_pct: number;
  reps_750_pct: number;
  material_500_pct: number;
  avg_daily_hours_total: number;
  avg_daily_hours_material: number;
}

export interface RepsEntriesEnvelope {
  user: RepsUser;
  entries: RepsEntryRow[];
  stats: RepsStats;
}

export interface RepsPropertyOption {
  name: string;
  source: 'bought' | 'prospect';
}

export interface RepsPerson {
  id: string;
  name: string;
  role?: string | null;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RepsConfigStatus {
  configured: boolean;
  detail?: string;
  sheet_tab?: string;
  bucket_name?: string;
  base_prefix?: string;
  min_description_length: number;
}

// Local timer state shape (persisted to localStorage per user).
export interface RepsTimerState {
  // null when stopwatch was never started
  startedAt: string | null; // ISO 8601 of the *current* run segment
  // Accumulated whole-segment ms from previous start/stop cycles within the
  // same logical session (resumes don't lose time on refresh).
  accumulatedMs: number;
  // The very first start of this session (used as the form's start_time).
  sessionStartedAt: string | null;
  // True while the stopwatch is actively running; false while paused/stopped.
  running: boolean;
}

export const EMPTY_REPS_TIMER_STATE: RepsTimerState = {
  startedAt: null,
  accumulatedMs: 0,
  sessionStartedAt: null,
  running: false,
};
