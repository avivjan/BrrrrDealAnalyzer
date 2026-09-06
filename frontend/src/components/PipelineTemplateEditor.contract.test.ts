// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";

import PipelineTemplateEditor from "./PipelineTemplateEditor.vue";
import { usePipelineTemplateStore } from "./../stores/pipelineTemplateStore";
import api from "../api";
import type { PipelineTemplateDto, PipelineTemplateStats } from "../types";

vi.mock("../api", () => ({
  default: {
    getPipelineTemplates: vi.fn(),
    updatePipelineTemplate: vi.fn(),
    getPipelineTemplateStats: vi.fn(),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const getTemplates = vi.mocked(api.getPipelineTemplates);
const updateTemplate = vi.mocked(api.updatePipelineTemplate);
const getStats = vi.mocked(api.getPipelineTemplateStats);

const template = (dealType: "BRRRR" | "FLIP"): PipelineTemplateDto => ({
  dealType,
  stages: [
    {
      id: "purchase",
      name: `${dealType} Purchase`,
      subStages: [{ id: "emd", label: "EMD" }],
    },
    { id: "closed", name: "Closed", subStages: [] },
  ],
});

const noStats = (dealType: "BRRRR" | "FLIP"): PipelineTemplateStats => ({
  dealType,
  stages: [],
  orphanStageDealCount: 0,
});

/** Mount closed, then open — the fetch hangs off the `open` watcher. */
async function openEditor(initialTab?: "BRRRR" | "FLIP") {
  const wrapper = mount(PipelineTemplateEditor, {
    props: { open: false, initialTab },
  });
  await wrapper.setProps({ open: true });
  await flushPromises();
  return wrapper;
}

type Editor = Awaited<ReturnType<typeof openEditor>>;

const stageName = (wrapper: Editor, index: number) =>
  wrapper.find<HTMLInputElement>(`[data-testid="pipeline.stage.${index}.name"]`);

const stageCount = (wrapper: Editor) =>
  wrapper.findAll('[data-testid^="pipeline.stage."]').filter((el) =>
    /^pipeline\.stage\.\d+$/.test(el.attributes("data-testid") ?? ""),
  ).length;

describe("PipelineTemplateEditor", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    getTemplates.mockResolvedValue([template("BRRRR"), template("FLIP")]);
    getStats.mockImplementation(async (type) => noStats(type));
    updateTemplate.mockImplementation(async (dealType, stages) => ({
      dealType,
      stages,
    }));
  });

  it("renders nothing while closed", () => {
    const wrapper = mount(PipelineTemplateEditor, { props: { open: false } });
    expect(wrapper.find('[data-testid="pipeline.root"]').exists()).toBe(false);
    expect(getTemplates).not.toHaveBeenCalled();
  });

  describe("opening", () => {
    it("loads the templates and both deal types' stats", async () => {
      await openEditor();

      expect(getTemplates).toHaveBeenCalledTimes(1);
      expect(getStats).toHaveBeenCalledWith("BRRRR");
      expect(getStats).toHaveBeenCalledWith("FLIP");
    });

    it("shows the fetched stages, not the built-in defaults", async () => {
      const wrapper = await openEditor();
      expect(stageName(wrapper, 0).element.value).toBe("BRRRR Purchase");
      expect(stageCount(wrapper)).toBe(2);
    });

    it("honours initialTab and switches the draft with the tab", async () => {
      const wrapper = await openEditor("FLIP");
      expect(stageName(wrapper, 0).element.value).toBe("FLIP Purchase");

      await wrapper.find('[data-testid="pipeline.tab.BRRRR"]').trigger("click");
      expect(stageName(wrapper, 0).element.value).toBe("BRRRR Purchase");
    });
  });

  describe("editing the draft", () => {
    it("appends a draft stage named 'New Stage'", async () => {
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.add-stage"]').trigger("click");

      expect(stageCount(wrapper)).toBe(3);
      expect(stageName(wrapper, 2).element.value).toBe("New Stage");
    });

    it("appends a draft substage named 'New Sub-stage'", async () => {
      const wrapper = await openEditor();

      await wrapper
        .find('[data-testid="pipeline.stage.1.add-substage"]')
        .trigger("click");

      const labels = wrapper
        .find('[data-testid="pipeline.stage.1"]')
        .findAll<HTMLInputElement>('[data-testid^="pipeline.substage."]')
        .filter((el) => el.element.tagName === "INPUT")
        .map((el) => el.element.value);
      expect(labels).toEqual(["New Sub-stage"]);
      expect(
        wrapper.find('[data-testid="pipeline.stage.1.substages-empty"]').exists(),
      ).toBe(false);
    });

    it("adds to the visible tab only, leaving the other draft alone", async () => {
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.add-stage"]').trigger("click");
      expect(stageCount(wrapper)).toBe(3);

      await wrapper.find('[data-testid="pipeline.tab.FLIP"]').trigger("click");
      expect(stageCount(wrapper)).toBe(2);
    });

    it("swaps two stages with the move buttons", async () => {
      const wrapper = await openEditor();

      await wrapper
        .find('[data-testid="pipeline.stage.1.move-up"]')
        .trigger("click");

      expect(stageName(wrapper, 0).element.value).toBe("Closed");
      expect(stageName(wrapper, 1).element.value).toBe("BRRRR Purchase");
    });

    it("never edits the store's stages until save", async () => {
      const wrapper = await openEditor();
      const store = usePipelineTemplateStore();

      await wrapper.find('[data-testid="pipeline.add-stage"]').trigger("click");

      expect(store.brrrStages).toHaveLength(2);
    });
  });

  describe("deleting a stage", () => {
    it("asks first, and keeps the stage on cancel", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.stage.0.delete"]').trigger("click");

      expect(confirmSpy).toHaveBeenCalledWith('Delete stage "BRRRR Purchase"?');
      expect(stageCount(wrapper)).toBe(2);
      confirmSpy.mockRestore();
    });

    it("removes the stage on accept", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.stage.0.delete"]').trigger("click");

      expect(stageCount(wrapper)).toBe(1);
      expect(stageName(wrapper, 0).element.value).toBe("Closed");
      confirmSpy.mockRestore();
    });

    it("warns how many deals sit on the stage when any do", async () => {
      getStats.mockImplementation(async (type) => ({
        dealType: type,
        orphanStageDealCount: 0,
        stages: [{ stageId: "purchase", dealCount: 3, substages: [] }],
      }));
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.stage.0.delete"]').trigger("click");

      expect(confirmSpy).toHaveBeenCalledWith(
        'Delete stage "BRRRR Purchase"? 3 deal(s) are currently on this stage and will be clamped to the nearest remaining stage.',
      );
      confirmSpy.mockRestore();
    });

    it("warns about existing completions when deleting a substage", async () => {
      getStats.mockImplementation(async (type) => ({
        dealType: type,
        orphanStageDealCount: 0,
        stages: [
          {
            stageId: "purchase",
            dealCount: 0,
            substages: [{ substageId: "emd", dealsWithCompletion: 2 }],
          },
        ],
      }));
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const wrapper = await openEditor();

      await wrapper
        .find('[data-testid="pipeline.substage.emd.delete"]')
        .trigger("click");

      expect(confirmSpy).toHaveBeenCalledWith(
        'Delete substage "EMD"? 2 deal(s) have completions for this substage. The legacy data will be ignored (not blocking advance) but kept on the deal.',
      );
      expect(wrapper.find('[data-testid="pipeline.substage.emd"]').exists()).toBe(
        true,
      );
      confirmSpy.mockRestore();
    });
  });

  describe("validation", () => {
    it("banners a blank stage name and disables Save", async () => {
      const wrapper = await openEditor();
      expect(
        wrapper.find('[data-testid="pipeline.validation-banner"]').exists(),
      ).toBe(false);

      await stageName(wrapper, 0).setValue("   ");

      const banner = wrapper.find('[data-testid="pipeline.validation-banner"]');
      expect(banner.exists()).toBe(true);
      expect(banner.text()).toContain('Stage "purchase" has no name.');
      expect(
        wrapper.find('[data-testid="pipeline.save"]').attributes("disabled"),
      ).toBeDefined();
    });

    it("banners a blank substage label", async () => {
      const wrapper = await openEditor();

      await wrapper
        .find('[data-testid="pipeline.substage.emd.name"]')
        .setValue("");

      expect(
        wrapper.find('[data-testid="pipeline.validation-banner"]').text(),
      ).toContain('Substage "emd" (in BRRRR Purchase) has no label.');
    });

    it("banners a pipeline emptied of every stage", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.stage.0.delete"]').trigger("click");
      await wrapper.find('[data-testid="pipeline.stage.0.delete"]').trigger("click");

      expect(
        wrapper.find('[data-testid="pipeline.validation-banner"]').text(),
      ).toContain("Pipeline must have at least one stage.");
      confirmSpy.mockRestore();
    });
  });

  describe("saving", () => {
    it("sends the active tab's draft, then emits saved and close", async () => {
      const wrapper = await openEditor();
      await wrapper.find('[data-testid="pipeline.add-stage"]').trigger("click");

      await wrapper.find('[data-testid="pipeline.save"]').trigger("click");
      await flushPromises();

      expect(updateTemplate).toHaveBeenCalledTimes(1);
      const [dealType, stages] = updateTemplate.mock.calls[0]!;
      expect(dealType).toBe("BRRRR");
      expect(stages.map((s) => s.name)).toEqual([
        "BRRRR Purchase",
        "Closed",
        "New Stage",
      ]);
      expect(wrapper.emitted("saved")).toHaveLength(1);
      expect(wrapper.emitted("close")).toHaveLength(1);
    });

    it("shows the server's detail and stays open when the save fails", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      updateTemplate.mockRejectedValue({
        response: { data: { detail: "Stage id in use" } },
      });
      const wrapper = await openEditor();

      await wrapper.find('[data-testid="pipeline.save"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="pipeline.save-error"]').text()).toBe(
        "Stage id in use",
      );
      expect(wrapper.emitted("saved")).toBeUndefined();
      expect(wrapper.emitted("close")).toBeUndefined();
      error.mockRestore();
    });
  });

  it("emits close from Cancel without saving", async () => {
    const wrapper = await openEditor();
    await wrapper.find('[data-testid="pipeline.cancel"]').trigger("click");

    expect(wrapper.emitted("close")).toHaveLength(1);
    expect(updateTemplate).not.toHaveBeenCalled();
  });
});
