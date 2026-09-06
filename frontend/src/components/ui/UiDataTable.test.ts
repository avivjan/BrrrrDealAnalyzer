// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import UiDataTable from "./UiDataTable.vue";

const columns = [
  { key: "date", label: "Date", sortable: true },
  { key: "amount", label: "Amount", align: "right" as const, numeric: true, sortable: true },
  { key: "note", label: "Note" },
];
const rows = [
  { id: 1, date: "2026-09-01", amount: 1200, note: "Rent" },
  { id: 2, date: "2026-09-03", amount: -450, note: "Repair" },
];

describe("UiDataTable", () => {
  it("renders headers and cells in order, aligned and numeric where told", () => {
    const wrapper = mount(UiDataTable, { props: { columns, rows, rowKey: "id" } });
    expect(wrapper.attributes("data-ui")).toBe("data-table");
    expect(wrapper.findAll("th").map((th) => th.text())).toEqual(["Date", "Amount", "Note"]);
    const firstRow = wrapper.findAll('[data-part="row"]')[0]!;
    expect(firstRow.findAll("td").map((td) => td.text())).toEqual(["2026-09-01", "1200", "Rent"]);
    expect(firstRow.findAll("td")[1]!.classes()).toEqual(expect.arrayContaining(["text-right", "numeric"]));
    expect(wrapper.get("thead").classes()).toContain("sticky");
  });

  it("never reorders rows itself; it announces the next sort and lets the parent act", async () => {
    const wrapper = mount(UiDataTable, { props: { columns, rows, rowKey: "id", sort: { key: "date", dir: "asc" } } });
    const [date, amount, note] = wrapper.findAll("th");
    expect(date!.attributes("aria-sort")).toBe("ascending");
    expect(amount!.attributes("aria-sort")).toBe("none");
    expect(note!.attributes("aria-sort")).toBeUndefined();
    expect(note!.find("button").exists()).toBe(false);

    await date!.get("button").trigger("click");
    expect(wrapper.emitted("update:sort")).toEqual([[{ key: "date", dir: "desc" }]]);
    await amount!.get("button").trigger("click");
    const sorts = wrapper.emitted("update:sort")!;
    expect(sorts[sorts.length - 1]).toEqual([{ key: "amount", dir: "asc" }]);
    // Rows are exactly what was passed.
    expect(wrapper.findAll('[data-part="row"]').map((r) => r.attributes("data-key") ?? r.findAll("td")[0]!.text())).toEqual([
      "2026-09-01",
      "2026-09-03",
    ]);
  });

  it("emits rowClick with the row, and makes rows focusable only when a listener exists", async () => {
    const silent = mount(UiDataTable, { props: { columns, rows, rowKey: "id" } });
    expect(silent.get('[data-part="row"]').attributes("tabindex")).toBeUndefined();

    const listening = mount(UiDataTable, { props: { columns, rows, rowKey: "id" }, attrs: { onRowClick: () => undefined } });
    const row = listening.findAll('[data-part="row"]')[1]!;
    expect(row.attributes("tabindex")).toBe("0");
    await row.trigger("click");
    await row.trigger("keydown.enter");
    expect(listening.emitted("rowClick")).toEqual([[rows[1]], [rows[1]]]);
  });

  it("renders cell and header slots, and the empty slot when there are no rows", () => {
    const wrapper = mount(UiDataTable, {
      props: { columns, rows, rowKey: "id" },
      slots: {
        "cell-amount": `<template #cell-amount="{ value }"><b>{{ value > 0 ? '+' : '' }}{{ value }}</b></template>`,
        "header-note": "Memo",
      },
    });
    expect(wrapper.findAll('[data-part="row"]')[0]!.findAll("td")[1]!.html()).toContain("<b>+1200</b>");
    expect(wrapper.findAll("th")[2]!.text()).toBe("Memo");

    const empty = mount(UiDataTable, { props: { columns, rows: [], rowKey: "id" }, slots: { empty: "No flows yet" } });
    expect(empty.get('[data-part="empty"]').text()).toBe("No flows yet");
    expect(empty.get('[data-part="empty"]').attributes("colspan")).toBe("3");
  });

  it("names itself for assistive tech when given a caption, and uses tokens only", () => {
    const wrapper = mount(UiDataTable, { props: { columns, rows, rowKey: "id", caption: "Transactions", dense: true } });
    expect(wrapper.get("caption").text()).toBe("Transactions");
    expect(wrapper.get("caption").classes()).toContain("sr-only");
    expect(wrapper.html()).not.toMatch(/\b(bg|text|border)-(gray|slate|blue|indigo|red|amber)-\d/);
  });
});
