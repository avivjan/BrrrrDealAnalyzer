import type { APIRequestContext } from '@playwright/test';
import { payloadFor, type DealType } from './payloads';

/**
 * Fixture data, arranged through the API rather than the UI.
 *
 * Every request here carries `x-e2e-seed: 1`. Nothing in this file goes
 * through the page, so the recorder — which listens inside the page — cannot
 * see it either way; the header makes the exclusion explicit rather than
 * incidental, so a future spec that does seed through the app still stays out
 * of the golden.
 *
 * The backend has no reset endpoint, so `resetDb()` sweeps: it lists every
 * mutable collection and deletes what it finds. With `workers: 1` and
 * `fullyParallel: false` that is safe, and it also collects the rows a spec
 * created *through the UI* (a duplicate, a moved deal, a recurring rule),
 * which id-tracking alone would miss.
 */

const SEED_HEADERS = { 'x-e2e-seed': '1' };

export interface SeededDeal {
  id: string;
  deal_type: DealType;
  address: string;
  section: number;
  stage: number;
  [key: string]: unknown;
}

export interface SeededBoughtDeal extends SeededDeal {
  boughtStage: string;
  completedSubstages: Record<string, boolean>;
}

/** The liquidity settings row is a singleton — snapshot it, don't delete it. */
interface LiquiditySettings {
  opening_balance_k: number;
  opening_balance_date: string;
  reserve_k: number;
}

interface PipelineTemplate {
  dealType: DealType;
  stages: unknown[];
}

export class Seeder {
  private baseline: LiquiditySettings | null = null;
  private templates: PipelineTemplate[] = [];

  constructor(
    private readonly request: APIRequestContext,
    private readonly apiOrigin: string,
  ) {}

  private url(path: string): string {
    return `${this.apiOrigin}${path}`;
  }

  private async json<T>(response: { ok(): boolean; status(): number; json(): Promise<unknown>; text(): Promise<string> }, what: string): Promise<T> {
    if (!response.ok()) {
      throw new Error(`${what} failed: ${response.status()} ${await response.text()}`);
    }
    return (await response.json()) as T;
  }

  /**
   * Remember the two rows `resetDb` cannot simply delete: the liquidity
   * settings singleton and the pipeline templates. A spec that edits either
   * would otherwise leak into every test that runs after it.
   */
  async snapshot(): Promise<void> {
    const settings = await this.request.get(this.url('/liquidity/settings'), {
      headers: SEED_HEADERS,
    });
    this.baseline = await this.json<LiquiditySettings>(settings, 'GET /liquidity/settings');

    const templates = await this.request.get(this.url('/pipeline-templates'), {
      headers: SEED_HEADERS,
    });
    this.templates = await this.json<PipelineTemplate[]>(templates, 'GET /pipeline-templates');
  }

  async seedActiveDeal(
    type: DealType = 'BRRRR',
    overrides: Record<string, unknown> = {},
  ): Promise<SeededDeal> {
    const body = { ...payloadFor(type), ...overrides };
    const response = await this.request.post(this.url('/active-deals'), {
      headers: SEED_HEADERS,
      data: body,
    });
    return this.json<SeededDeal>(response, 'POST /active-deals');
  }

  /** An active deal promoted into the bought pipeline, as the UI would do it. */
  async seedBoughtDeal(
    type: DealType = 'BRRRR',
    overrides: Record<string, unknown> = {},
  ): Promise<SeededBoughtDeal> {
    const active = await this.seedActiveDeal(type, { stage: 3, ...overrides });
    const response = await this.request.post(
      this.url(`/bought-deals/from-active/${active.id}?deal_type=${type}`),
      { headers: SEED_HEADERS },
    );
    return this.json<SeededBoughtDeal>(response, 'POST /bought-deals/from-active');
  }

  /** Move a bought deal onto a named pipeline stage, with substages given. */
  async setBoughtStage(
    deal: SeededBoughtDeal,
    boughtStage: string,
    completedSubstages: Record<string, boolean> = {},
  ): Promise<SeededBoughtDeal> {
    const next = { ...deal, boughtStage, completedSubstages };
    const response = await this.request.put(this.url(`/bought-deals/${deal.id}`), {
      headers: SEED_HEADERS,
      data: next,
    });
    return this.json<SeededBoughtDeal>(response, 'PUT /bought-deals/{id}');
  }

  async listActiveDeals(): Promise<SeededDeal[]> {
    const response = await this.request.get(this.url('/active-deals'), {
      headers: SEED_HEADERS,
    });
    return this.json<SeededDeal[]>(response, 'GET /active-deals');
  }

  async listPipelineTemplates(): Promise<
    { dealType: DealType; stages: { id: string; name: string; subStages: { id: string; label: string }[] }[] }[]
  > {
    const response = await this.request.get(this.url('/pipeline-templates'), {
      headers: SEED_HEADERS,
    });
    return this.json(response, 'GET /pipeline-templates');
  }

  async listBoughtDeals(): Promise<SeededBoughtDeal[]> {
    const response = await this.request.get(this.url('/bought-deals'), {
      headers: SEED_HEADERS,
    });
    return this.json<SeededBoughtDeal[]>(response, 'GET /bought-deals');
  }

  /** Delete everything mutable and restore the settings singleton. */
  async resetDb(): Promise<void> {
    for (const deal of await this.listBoughtDeals()) {
      await this.request.delete(
        this.url(`/bought-deals/${deal.id}?deal_type=${deal.deal_type ?? 'BRRRR'}`),
        { headers: SEED_HEADERS },
      );
    }
    for (const deal of await this.listActiveDeals()) {
      await this.request.delete(
        this.url(`/active-deals/${deal.id}?deal_type=${deal.deal_type ?? 'BRRRR'}`),
        { headers: SEED_HEADERS },
      );
    }
    for (const path of ['/liquidity/transactions', '/liquidity/recurring', '/reps/people']) {
      const response = await this.request.get(this.url(path), { headers: SEED_HEADERS });
      if (!response.ok()) continue;
      const rows = (await response.json()) as { id: string }[];
      for (const row of rows) {
        await this.request.delete(this.url(`${path}/${row.id}`), { headers: SEED_HEADERS });
      }
    }
    if (this.baseline) {
      const response = await this.request.get(this.url('/liquidity/settings'), {
        headers: SEED_HEADERS,
      });
      const current = await this.json<LiquiditySettings>(response, 'GET /liquidity/settings');
      const drifted =
        current.opening_balance_k !== this.baseline.opening_balance_k ||
        current.opening_balance_date !== this.baseline.opening_balance_date ||
        current.reserve_k !== this.baseline.reserve_k;
      if (drifted) {
        await this.request.put(this.url('/liquidity/settings'), {
          headers: SEED_HEADERS,
          data: this.baseline,
        });
      }
    }
    if (this.templates.length > 0) {
      const response = await this.request.get(this.url('/pipeline-templates'), {
        headers: SEED_HEADERS,
      });
      const current = await this.json<PipelineTemplate[]>(response, 'GET /pipeline-templates');
      for (const original of this.templates) {
        const now = current.find((row) => row.dealType === original.dealType);
        if (now && JSON.stringify(now.stages) === JSON.stringify(original.stages)) continue;
        await this.request.put(this.url(`/pipeline-templates/${original.dealType}`), {
          headers: SEED_HEADERS,
          data: { stages: original.stages },
        });
      }
    }
  }
}
