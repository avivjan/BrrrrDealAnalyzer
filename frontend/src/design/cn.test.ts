import { describe, expect, it } from "vitest";

import { cn } from "./cn";

/**
 * `cn` is two libraries in a trench coat, so the tests are about the seam:
 * clsx decides *which* class names are in play, tailwind-merge decides which
 * of the surviving ones actually reach the DOM.
 */
describe("cn", () => {
  describe("clsx's half — collecting class names", () => {
    it("joins plain strings", () => {
      expect(cn("flex", "items-center")).toBe("flex items-center");
    });

    it("drops falsy entries instead of printing 'false' or 'undefined'", () => {
      expect(cn("flex", false, null, undefined, "", "gap-2")).toBe("flex gap-2");
    });

    it("takes the truthy keys of an object", () => {
      expect(cn({ "font-bold": true, italic: false, underline: true })).toBe(
        "font-bold underline",
      );
    });

    it("flattens nested arrays", () => {
      expect(cn(["flex", ["gap-2", ["p-4"]]])).toBe("flex gap-2 p-4");
    });

    it("returns an empty string when there is nothing to emit", () => {
      expect(cn()).toBe("");
      expect(cn(false, undefined)).toBe("");
    });
  });

  describe("tailwind-merge's half — last conflicting utility wins", () => {
    it("keeps the later class of a conflicting pair", () => {
      expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
    });

    it("collapses an exact repeat", () => {
      expect(cn("p-4", "p-4")).toBe("p-4");
    });

    it("resolves conflicts between this project's semantic colour tokens", () => {
      // The whole point of the helper: a caller's `bg-primary` must beat a
      // component's default `bg-surface`, not sit next to it and lose to
      // whichever rule the stylesheet happens to emit last. tailwind-merge
      // reads `bg-*` / `text-*` as colour groups whatever the scale key is,
      // so the semantic names work with no extra configuration.
      expect(cn("bg-surface", "bg-primary")).toBe("bg-primary");
      expect(cn("bg-primary", "bg-fg-muted/60")).toBe("bg-fg-muted/60");
      expect(cn("text-fg-muted", "text-fg")).toBe("text-fg");
    });

    it("does not merge the custom radius scale — a known, harmless gap", () => {
      // tailwind-merge's stock config enumerates `rounded-{none,sm,md,lg,…}`
      // and has no way to learn that `ctl`/`card`/`panel` belong to the same
      // group, so both survive and stylesheet order decides. Nothing stacks
      // two radii today; if that changes, the fix is `extendTailwindMerge`
      // with the project's radius keys, not a change at the call site.
      expect(cn("rounded-ctl", "rounded-panel")).toBe("rounded-ctl rounded-panel");
    });

    it("leaves non-conflicting utilities from both sides alone", () => {
      expect(cn("text-fg shadow-1", "bg-surface")).toBe(
        "text-fg shadow-1 bg-surface",
      );
    });

    it("treats a variant as its own scope", () => {
      // `hover:bg-*` does not conflict with an unprefixed `bg-*`.
      expect(cn("bg-surface", "hover:bg-surface-muted")).toBe(
        "bg-surface hover:bg-surface-muted",
      );
    });
  });
});
