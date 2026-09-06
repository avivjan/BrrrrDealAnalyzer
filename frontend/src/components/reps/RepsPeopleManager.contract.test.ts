// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";

import RepsPeopleManager from "./RepsPeopleManager.vue";
import { useRepsStore } from "../../stores/repsStore";
import type { RepsPerson } from "../../types/reps";

vi.mock("../../api", () => ({
  default: {
    getRepsPeople: vi.fn().mockResolvedValue([]),
    createRepsPerson: vi.fn(),
    updateRepsPerson: vi.fn(),
    deleteRepsPerson: vi.fn(),
  },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const person = (over: Partial<RepsPerson> = {}): RepsPerson => ({
  id: "p1",
  name: "Dana Plumber",
  role: "Plumber",
  notes: "24h call-out",
  ...over,
});

function mountManager(people: RepsPerson[] = []) {
  const store = useRepsStore();
  store.people = people;
  return { wrapper: mount(RepsPeopleManager), store };
}

describe("RepsPeopleManager", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("invites the user to add someone when the list is empty", () => {
    const { wrapper } = mountManager();
    expect(wrapper.find('[data-testid="repspeople.empty"]').text()).toBe(
      "No people yet. Add contractors, agents, lenders, etc. to tag on log entries.",
    );
  });

  it("lists each person with their role and notes", () => {
    const { wrapper } = mountManager([person()]);
    const row = wrapper.find('[data-testid="repspeople.person.p1"]');

    expect(row.text()).toContain("Dana Plumber");
    expect(row.text()).toContain("Plumber");
    expect(row.text()).toContain("24h call-out");
    expect(wrapper.text()).toContain("1 contacts");
  });

  describe("adding", () => {
    it("sends the trimmed fields to the store and clears the boxes", async () => {
      const { wrapper, store } = mountManager();
      const addPerson = vi
        .spyOn(store, "addPerson")
        .mockResolvedValue(person({ name: "Ray Roofer" }));

      await wrapper.find('[data-testid="repspeople.new-name"]').setValue("  Ray Roofer ");
      await wrapper.find('[data-testid="repspeople.new-role"]').setValue(" Roofer ");
      await wrapper.find('[data-testid="repspeople.new-notes"]').setValue(" Cheap ");
      await wrapper.find('[data-testid="repspeople.add"]').trigger("click");
      await flushPromises();

      expect(addPerson).toHaveBeenCalledWith({
        name: "Ray Roofer",
        role: "Roofer",
        notes: "Cheap",
      });
      expect(
        wrapper.find<HTMLInputElement>('[data-testid="repspeople.new-name"]').element
          .value,
      ).toBe("");
    });

    it("omits an empty role and notes rather than sending blanks", async () => {
      const { wrapper, store } = mountManager();
      const addPerson = vi.spyOn(store, "addPerson").mockResolvedValue(person());

      await wrapper.find('[data-testid="repspeople.new-name"]').setValue("Solo");
      await wrapper.find('[data-testid="repspeople.add"]').trigger("click");
      await flushPromises();

      expect(addPerson).toHaveBeenCalledWith({
        name: "Solo",
        role: undefined,
        notes: undefined,
      });
    });

    it("does nothing without a name", async () => {
      const { wrapper, store } = mountManager();
      const addPerson = vi.spyOn(store, "addPerson");

      await wrapper.find('[data-testid="repspeople.new-name"]').setValue("   ");
      await wrapper.find('[data-testid="repspeople.add"]').trigger("click");
      await flushPromises();

      expect(addPerson).not.toHaveBeenCalled();
    });

    it("shows the server's detail when the add is rejected", async () => {
      const { wrapper, store } = mountManager();
      vi.spyOn(store, "addPerson").mockRejectedValue({
        response: { data: { detail: "Name already exists" } },
      });

      await wrapper.find('[data-testid="repspeople.new-name"]').setValue("Dupe");
      await wrapper.find('[data-testid="repspeople.add"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="repspeople.error"]').text()).toBe(
        "Name already exists",
      );
      // The typed name survives so the user can correct it.
      expect(
        wrapper.find<HTMLInputElement>('[data-testid="repspeople.new-name"]').element
          .value,
      ).toBe("Dupe");
    });
  });

  describe("removing", () => {
    const COPY = "Delete this person? Existing log entries will keep the name.";

    it("asks first and does nothing on cancel", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
      const { wrapper, store } = mountManager([person()]);
      const removePerson = vi.spyOn(store, "removePerson");

      await wrapper.find('[data-testid="repspeople.person.p1.delete"]').trigger("click");
      await flushPromises();

      expect(confirmSpy).toHaveBeenCalledWith(COPY);
      expect(removePerson).not.toHaveBeenCalled();
      confirmSpy.mockRestore();
    });

    it("removes the person on accept", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const { wrapper, store } = mountManager([person()]);
      const removePerson = vi.spyOn(store, "removePerson").mockResolvedValue(undefined);

      await wrapper.find('[data-testid="repspeople.person.p1.delete"]').trigger("click");
      await flushPromises();

      expect(removePerson).toHaveBeenCalledWith("p1");
      confirmSpy.mockRestore();
    });

    it("shows the server's detail when the delete is rejected", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const { wrapper, store } = mountManager([person()]);
      vi.spyOn(store, "removePerson").mockRejectedValue({
        response: { data: { detail: "Person is referenced by an entry" } },
      });

      await wrapper.find('[data-testid="repspeople.person.p1.delete"]').trigger("click");
      await flushPromises();

      expect(wrapper.find('[data-testid="repspeople.error"]').text()).toBe(
        "Person is referenced by an entry",
      );
      confirmSpy.mockRestore();
    });
  });

  describe("editing in place", () => {
    it("swaps the row for its edit fields, seeded from the person", async () => {
      const { wrapper } = mountManager([person()]);

      await wrapper.find('[data-testid="repspeople.person.p1.edit"]').trigger("click");

      expect(
        wrapper.find<HTMLInputElement>('[data-testid="repspeople.person.p1.edit-name"]')
          .element.value,
      ).toBe("Dana Plumber");
      expect(
        wrapper.find<HTMLInputElement>('[data-testid="repspeople.person.p1.edit-role"]')
          .element.value,
      ).toBe("Plumber");
    });

    it("sends the edited fields to the store and closes the editor", async () => {
      const { wrapper, store } = mountManager([person()]);
      const updatePerson = vi
        .spyOn(store, "updatePerson")
        .mockResolvedValue(person({ name: "Dana P." }));

      await wrapper.find('[data-testid="repspeople.person.p1.edit"]').trigger("click");
      await wrapper
        .find('[data-testid="repspeople.person.p1.edit-name"]')
        .setValue("  Dana P.  ");
      await wrapper.find('[data-testid="repspeople.person.p1.save"]').trigger("click");
      await flushPromises();

      expect(updatePerson).toHaveBeenCalledWith("p1", {
        name: "Dana P.",
        role: "Plumber",
        notes: "24h call-out",
      });
      expect(
        wrapper.find('[data-testid="repspeople.person.p1.edit-name"]').exists(),
      ).toBe(false);
    });

    it("abandons the edit on Cancel", async () => {
      const { wrapper, store } = mountManager([person()]);
      const updatePerson = vi.spyOn(store, "updatePerson");

      await wrapper.find('[data-testid="repspeople.person.p1.edit"]').trigger("click");
      await wrapper
        .find('[data-testid="repspeople.person.p1.edit-name"]')
        .setValue("Discarded");
      await wrapper.find('[data-testid="repspeople.person.p1.cancel"]').trigger("click");

      expect(updatePerson).not.toHaveBeenCalled();
      expect(wrapper.find('[data-testid="repspeople.person.p1"]').text()).toContain(
        "Dana Plumber",
      );
    });
  });
});
