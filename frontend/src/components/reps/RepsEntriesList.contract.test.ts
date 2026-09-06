// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import RepsEntriesList from "./RepsEntriesList.vue";
import type { RepsEntryRow } from "../../types/reps";

function entry(over: Partial<RepsEntryRow> = {}): RepsEntryRow {
  return {
    created_at: "2026-05-01T12:00:00.000Z",
    user: "Aviv2026",
    property_name: "2286 Laurel Grove",
    activity_category: "Rehab / Construction",
    description: "Met the plumber on site",
    start_time: "2026-05-01T09:00:00.000Z",
    end_time: "2026-05-01T11:00:00.000Z",
    total_hours: 2,
    evidence_link: null,
    evidence_items: [],
    location: "Jacksonville, FL",
    material_participation_rentals: true,
    people_involved: ["Dana"],
    ...over,
  };
}

function mountList(props: Record<string, unknown> = {}) {
  return mount(RepsEntriesList, { props: { entries: [], ...props } });
}

type List = ReturnType<typeof mountList>;

const rows = (wrapper: List) =>
  wrapper.findAll('[data-testid^="repsentries.entry."]').filter((el) =>
    /^repsentries\.entry\.\d+$/.test(el.attributes("data-testid") ?? ""),
  );

describe("RepsEntriesList", () => {
  describe("the four states", () => {
    it("shows a loading line while fetching", () => {
      const wrapper = mountList({ loading: true, entries: [entry()] });
      expect(wrapper.find('[data-testid="repsentries.loading"]').text()).toContain(
        "Loading entries from sheet...",
      );
      expect(rows(wrapper)).toHaveLength(0);
    });

    it("shows the error instead of the rows", () => {
      const wrapper = mountList({
        error: "Sheet is not shared with the service account",
        entries: [entry()],
      });
      expect(wrapper.find('[data-testid="repsentries.error"]').text()).toBe(
        "Sheet is not shared with the service account",
      );
      expect(rows(wrapper)).toHaveLength(0);
    });

    it("prefers loading over an error when both are set", () => {
      const wrapper = mountList({ loading: true, error: "boom" });
      expect(wrapper.find('[data-testid="repsentries.loading"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="repsentries.error"]').exists()).toBe(false);
    });

    it("says nothing matched when the list comes back empty", () => {
      expect(mountList().find('[data-testid="repsentries.empty"]').text()).toBe(
        "No entries match your filters.",
      );
    });

    it("lists the entries otherwise", () => {
      const wrapper = mountList({ entries: [entry()] });
      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("Met the plumber on site");
      expect(wrapper.text()).toContain("2.00h");
    });
  });

  it("puts the most recent entry first", () => {
    const wrapper = mountList({
      entries: [
        entry({ description: "Older", start_time: "2026-04-01T09:00:00.000Z" }),
        entry({ description: "Newer", start_time: "2026-06-01T09:00:00.000Z" }),
      ],
    });

    expect(rows(wrapper)[0]!.text()).toContain("Newer");
    expect(rows(wrapper)[1]!.text()).toContain("Older");
  });

  describe("the search box", () => {
    const entries = [
      entry({ description: "Met the plumber", property_name: "Laurel Grove" }),
      entry({ description: "Called the lender", property_name: "Oak Street" }),
    ];

    it("narrows to matching descriptions", async () => {
      const wrapper = mountList({ entries });
      await wrapper.find('[data-testid="repsentries.search"]').setValue("plumber");

      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("Met the plumber");
    });

    it("also searches the property, category and location", async () => {
      const wrapper = mountList({ entries });
      await wrapper.find('[data-testid="repsentries.search"]').setValue("oak street");

      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("Called the lender");
    });

    it("ignores case", async () => {
      const wrapper = mountList({ entries });
      await wrapper.find('[data-testid="repsentries.search"]').setValue("PLUMBER");
      expect(rows(wrapper)).toHaveLength(1);
    });

    it("falls through to the empty state when nothing matches", async () => {
      const wrapper = mountList({ entries });
      await wrapper.find('[data-testid="repsentries.search"]').setValue("zzz");
      expect(wrapper.find('[data-testid="repsentries.empty"]').exists()).toBe(true);
    });
  });

  describe("the material-participation filter", () => {
    const entries = [
      entry({ description: "Counts for 500h", material_participation_rentals: true }),
      entry({ description: "Counts for 750h", material_participation_rentals: false }),
    ];

    it("shows both buckets by default", () => {
      expect(rows(mountList({ entries }))).toHaveLength(2);
    });

    it("keeps only material entries", async () => {
      const wrapper = mountList({ entries });
      await wrapper
        .find('[data-testid="repsentries.filter-material"]')
        .setValue("material");

      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("Counts for 500h");
      expect(wrapper.text()).toContain("500h");
    });

    it("keeps only non-material entries", async () => {
      const wrapper = mountList({ entries });
      await wrapper
        .find('[data-testid="repsentries.filter-material"]')
        .setValue("non-material");

      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("Counts for 750h");
    });
  });

  describe("the person filter", () => {
    it("is hidden when nobody is tagged on any entry", () => {
      const wrapper = mountList({ entries: [entry({ people_involved: [] })] });
      expect(
        wrapper.find('[data-testid="repsentries.filter-person"]').exists(),
      ).toBe(false);
    });

    it("offers every tagged person, de-duplicated and sorted", () => {
      const wrapper = mountList({
        entries: [
          entry({ people_involved: ["Zoe", "Dana"] }),
          entry({ people_involved: ["Dana"] }),
        ],
      });

      const options = wrapper
        .findAll('[data-testid^="repsentries.person-option."]')
        .map((el) => el.text());
      expect(options).toEqual(["Dana", "Zoe"]);
    });

    it("narrows to the entries that person appears on", async () => {
      const wrapper = mountList({
        entries: [
          entry({ description: "With Dana", people_involved: ["Dana"] }),
          entry({ description: "With Zoe", people_involved: ["Zoe"] }),
        ],
      });

      await wrapper.find('[data-testid="repsentries.filter-person"]').setValue("Zoe");

      expect(rows(wrapper)).toHaveLength(1);
      expect(wrapper.text()).toContain("With Zoe");
    });
  });

  describe("evidence links", () => {
    it("renders one labelled chip per evidence item", () => {
      const wrapper = mountList({
        entries: [
          entry({
            evidence_items: [
              { url: "https://example.com/a.jpg", label: "Site photo" },
              { url: "https://example.com/b.pdf", label: "" },
            ],
          }),
        ],
      });

      const first = wrapper.find('[data-testid="repsentries.entry.0.evidence.0"]');
      expect(first.attributes("href")).toBe("https://example.com/a.jpg");
      expect(first.text()).toBe("Site photo");
      expect(
        wrapper.find('[data-testid="repsentries.entry.0.evidence.1"]').text(),
      ).toBe("Evidence 2");
    });

    it("falls back to the legacy single link", () => {
      const wrapper = mountList({
        entries: [entry({ evidence_link: "https://example.com/legacy.pdf" })],
      });

      expect(
        wrapper
          .find('[data-testid="repsentries.entry.0.evidence-legacy"]')
          .attributes("href"),
      ).toBe("https://example.com/legacy.pdf");
    });

    it("shows a non-URL evidence note as plain text, not a link", () => {
      const wrapper = mountList({
        entries: [entry({ evidence_link: "photos on my phone" })],
      });

      expect(
        wrapper.find('[data-testid="repsentries.entry.0.evidence-legacy"]').exists(),
      ).toBe(false);
      expect(wrapper.text()).toContain("photos on my phone");
    });
  });
});
