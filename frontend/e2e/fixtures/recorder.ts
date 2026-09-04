import { expect, type Page } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

/**
 * Network-contract recorder.
 *
 * Every request the *app* makes to the API origin is reduced to a stable,
 * browser-independent shape and compared against a committed golden. That is
 * the whole point of Phase 0: a visual overhaul must not move a single byte on
 * the wire, and "I clicked around and it looked fine" cannot prove that.
 *
 * ## Why this listens inside the page rather than on `page.on('request')`
 *
 * Because the contract belongs to the app, not to the network stack. WebKit
 * coalesces two identical, concurrently-issued `GET`s into a single wire
 * request; Chromium sends both. `App.vue` and `MyDeals.vue` each fetch
 * `/active-deals` on a fresh `/my-deals` load, so the same code produced a
 * 4-request golden on one engine and a 3-request one on the other — a
 * difference that says nothing about the app and would have to be papered over
 * with a per-engine exception. Wrapping `XMLHttpRequest` and `fetch` records
 * what the app *asked for*, which is identical everywhere, and drops CORS
 * preflights for free.
 *
 * ## What is deliberately not recorded, and why
 *  - Responses. The backend owns those and `verify_regression.py` already
 *    freezes them; recording list responses here would fail on nothing but
 *    SQLite row order. The exception is a blob download, where the *only*
 *    interesting part is the status and content type.
 *  - Anything carrying `x-e2e-seed: 1`. That is the suite arranging its own
 *    fixtures, not the app talking.
 *  - Volatile values, redacted by key (see `REDACTED_KEYS`). A uuid or a
 *    timestamp differs on every run and says nothing about the contract.
 *  - The bytes of an uploaded file. A multipart body is reduced to its field
 *    names and a file count.
 */

const REDACTED = '<redacted>';

/** Keys whose value is volatile and is replaced wholesale. */
const REDACTED_KEYS = new Set([
  'id',
  'created_at',
  'updated_at',
  'sourceDealId',
  'source_deal_id',
  'opening_balance_date',
  'spreadsheet_id',
  'appended_range',
]);

/** Any key ending in `_id` is an identifier too (`recurring_rule_id`, ...). */
function isRedactedKey(key: string): boolean {
  return REDACTED_KEYS.has(key) || key.endsWith('_id');
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Paths whose response body is a blob; status + content type is the contract. */
const BLOB_PREFIX = '/reports/';

export interface RecordedRequest {
  method: string;
  path: string;
  query?: Record<string, string>;
  body?: unknown;
  /** Blob downloads only: the two things about the response that matter. */
  response?: { status: number; contentType: string | null };
}

export interface Contract {
  requests: RecordedRequest[];
  /** Optional rendered-text snapshot, for flows that assert on output. */
  rendered?: Record<string, string>;
}

/** What the in-page probe hands back over the exposed binding. */
interface ProbePayload {
  id: number;
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string | null;
  multipart?: { fields: string[]; files: number } | null;
  response?: { status: number; contentType: string | null };
}

export const isRecording = process.env.PW_RECORD === '1';

const GOLDEN_DIR = resolve(process.cwd(), 'e2e/golden');

function goldenPath(name: string): string {
  return resolve(GOLDEN_DIR, `${name}.json`);
}

/** Replace uuid path segments so `/active-deals/<uuid>` reads `/active-deals/{id}`. */
function normalizePath(pathname: string): string {
  return pathname
    .split('/')
    .map((segment) => (UUID_RE.test(segment) ? '{id}' : segment))
    .join('/');
}

function redact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      const raw = (value as Record<string, unknown>)[key];
      out[key] = isRedactedKey(key) && raw !== null ? REDACTED : redact(raw);
    }
    return out;
  }
  return value;
}

function sortedQuery(url: URL): Record<string, string> | undefined {
  const keys = [...url.searchParams.keys()].sort();
  if (keys.length === 0) return undefined;
  const out: Record<string, string> = {};
  for (const key of keys) out[key] = url.searchParams.get(key) ?? '';
  return out;
}

/**
 * The in-page probe. Wraps both transports the app could use, reports each
 * request the moment it is handed over, and reports a blob response's status
 * when it lands. Nothing here reads or alters a payload the app sends.
 */
const PROBE_SCRIPT = `(() => {
  if (window.__e2eProbeInstalled) return;
  window.__e2eProbeInstalled = true;

  let seq = 0;
  const backlog = [];

  const emit = (payload) => {
    const sink = window.__e2eRecord;
    if (!sink) {
      backlog.push(payload);
      // A microtask, never a timer: the suite runs with a frozen clock.
      Promise.resolve().then(emit.bind(null, null));
      return;
    }
    while (backlog.length) sink(backlog.shift());
    if (payload) sink(payload);
  };

  const summarize = (form) => {
    const fields = [];
    let files = 0;
    for (const [name, value] of form.entries()) {
      const isFile =
        (typeof File !== 'undefined' && value instanceof File) ||
        (typeof Blob !== 'undefined' && value instanceof Blob);
      if (isFile) files += 1;
      else fields.push(name);
    }
    return { fields: fields.sort(), files };
  };

  const describe = (id, method, url, headers, body) => {
    const payload = { id, method: String(method).toUpperCase(), url: String(url), headers, body: null, multipart: null };
    if (typeof FormData !== 'undefined' && body instanceof FormData) payload.multipart = summarize(body);
    else if (typeof body === 'string') payload.body = body;
    return payload;
  };

  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__e2e = { method: method, url: url, headers: {} };
    return open.apply(this, arguments);
  };

  const setRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
    if (this.__e2e) this.__e2e.headers[String(name).toLowerCase()] = String(value);
    return setRequestHeader.apply(this, arguments);
  };

  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (body) {
    const meta = this.__e2e;
    if (meta) {
      const id = ++seq;
      emit(describe(id, meta.method, meta.url, meta.headers, body));
      this.addEventListener('load', () => {
        emit({ id: id, response: { status: this.status, contentType: this.getResponseHeader('content-type') } });
      });
    }
    return send.apply(this, arguments);
  };

  const nativeFetch = window.fetch;
  window.fetch = function (input, init) {
    const request = input && typeof input === 'object' && 'url' in input ? input : null;
    const url = request ? request.url : String(input);
    const method = (init && init.method) || (request && request.method) || 'GET';
    const headers = {};
    const rawHeaders = (init && init.headers) || (request && request.headers);
    if (rawHeaders && typeof rawHeaders.forEach === 'function') {
      rawHeaders.forEach((value, name) => { headers[String(name).toLowerCase()] = String(value); });
    } else if (rawHeaders) {
      for (const name of Object.keys(rawHeaders)) headers[name.toLowerCase()] = String(rawHeaders[name]);
    }
    const id = ++seq;
    emit(describe(id, method, url, headers, init && init.body));
    return nativeFetch.apply(this, arguments).then((response) => {
      emit({ id: id, response: { status: response.status, contentType: response.headers.get('content-type') } });
      return response;
    });
  };
})();`;

export class NetworkRecorder {
  readonly requests: RecordedRequest[] = [];
  private readonly byId = new Map<number, RecordedRequest>();
  private readonly awaitingResponse = new Set<number>();

  constructor(
    private readonly page: Page,
    private readonly apiOrigin: string,
  ) {}

  async install(): Promise<void> {
    await this.page.exposeFunction('__e2eRecord', (payload: ProbePayload | null) => {
      if (payload) this.onPayload(payload);
    });
    await this.page.addInitScript(PROBE_SCRIPT);
  }

  private onPayload(payload: ProbePayload): void {
    if (payload.response) {
      // Only a blob download keeps its response. Every other endpoint's answer
      // belongs to the backend's own golden harness, not to this one.
      if (!this.awaitingResponse.has(payload.id)) return;
      const record = this.byId.get(payload.id);
      if (record) record.response = payload.response;
      this.awaitingResponse.delete(payload.id);
      return;
    }
    if (!payload.url || !payload.method) return;

    let url: URL;
    try {
      url = new URL(payload.url, this.apiOrigin);
    } catch {
      return;
    }
    if (url.origin !== this.apiOrigin) return;
    if (payload.headers?.['x-e2e-seed'] === '1') return;

    const record: RecordedRequest = {
      method: payload.method,
      path: normalizePath(url.pathname),
    };
    const query = sortedQuery(url);
    if (query) record.query = query;

    if (payload.multipart) {
      record.body = payload.multipart;
    } else if (payload.body) {
      try {
        record.body = redact(JSON.parse(payload.body));
      } catch {
        record.body = payload.body;
      }
    }

    if (url.pathname.startsWith(BLOB_PREFIX)) this.awaitingResponse.add(payload.id);

    this.byId.set(payload.id, record);
    this.requests.push(record);
  }

  /** Clear everything recorded so far (page load noise, arrange steps, ...). */
  reset(): void {
    this.requests.length = 0;
    this.byId.clear();
    this.awaitingResponse.clear();
  }

  /**
   * Wait until every blob response this recorder is still expecting has been
   * attached. Any assertion on a recorded `response` has to await this first.
   */
  async settled(timeoutMs = 10_000): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (this.awaitingResponse.size > 0 && Date.now() < deadline) {
      await this.page.waitForTimeout(50);
    }
  }

  /** Wait until no new request has arrived for `quietMs`. */
  async waitForQuiet(quietMs = 400, timeoutMs = 10_000): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    let seen = this.requests.length;
    let quietSince = Date.now();
    while (Date.now() < deadline) {
      await this.page.waitForTimeout(50);
      if (this.requests.length !== seen) {
        seen = this.requests.length;
        quietSince = Date.now();
      } else if (Date.now() - quietSince >= quietMs) {
        return;
      }
    }
  }

  /**
   * Compare the recorded sequence against `e2e/golden/<name>.json`, or write
   * it when `PW_RECORD=1`. Order matters.
   */
  async expectContract(
    name: string,
    extra?: { rendered?: Record<string, string> },
  ): Promise<void> {
    if (isRecording) {
      await this.waitForQuiet();
      await this.settled();
      const contract: Contract = { requests: this.requests };
      if (extra?.rendered) contract.rendered = extra.rendered;
      mkdirSync(dirname(goldenPath(name)), { recursive: true });
      writeFileSync(goldenPath(name), `${JSON.stringify(contract, null, 2)}\n`);
      return;
    }

    const file = goldenPath(name);
    if (!existsSync(file)) {
      throw new Error(
        `Missing network-contract golden "${name}". Record it with \`npm run e2e:record\`.`,
      );
    }
    const golden = JSON.parse(readFileSync(file, 'utf8')) as Contract;

    // Give late requests a chance to land before declaring a mismatch.
    await expect
      .poll(() => this.requests.length, {
        message: `request count for contract "${name}"`,
      })
      .toBe(golden.requests.length);
    await this.settled();

    expect(this.requests, `network contract "${name}"`).toEqual(golden.requests);
    if (golden.rendered) {
      expect(extra?.rendered, `rendered snapshot for "${name}"`).toEqual(
        golden.rendered,
      );
    }
  }

  /** Assert nothing at all reached the API since the last `reset()`. */
  async expectNoRequests(message = 'expected no API traffic'): Promise<void> {
    await this.page.waitForTimeout(400);
    expect(this.requests, message).toEqual([]);
  }

  /** Every recorded request matching a predicate, for targeted assertions. */
  matching(predicate: (request: RecordedRequest) => boolean): RecordedRequest[] {
    return this.requests.filter(predicate);
  }
}
