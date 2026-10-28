// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import InspectionReportDeliveryStatus from "./InspectionReportDeliveryStatus.vue";

describe("InspectionReportDeliveryStatus", () => {
  it.each([
    ["delivered", "Report e-mailed and saved to Drive"],
    ["sending", "Sending the report…"],
    ["will_retry", "it will retry automatically"],
  ] as const)("shows %s", (status, text) => {
    const wrapper = mount(InspectionReportDeliveryStatus, { props: { reportDeliveryStatus: status } });
    expect(wrapper.get('[data-testid="inspection.report-status"]').attributes("data-state")).toBe(status);
    expect(wrapper.text()).toContain(text);
  });

  it("shows nothing before the first finish", () => {
    const wrapper = mount(InspectionReportDeliveryStatus, { props: { reportDeliveryStatus: null } });
    expect(wrapper.find('[data-testid="inspection.report-status"]').exists()).toBe(false);
  });
});
