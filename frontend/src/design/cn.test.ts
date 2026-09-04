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

    it("lets a semantic colour beat a stock Tailwind one, and the reverse", () => {
      expect(cn("bg-gray-50", "bg-page")).toBe("bg-page");
      expect(cn("bg-page", "bg-gray-50")).toBe("bg-gray-50");
    });

    /**
     * The four scales `tailwind.config.js` adds keys to. tailwind-merge can
     * infer a colour group from any scale key, but not these: a bare
     * `rounded-card` is indistinguishable from a class it has never heard of.
     * So `cn` teaches it the project's keys through `extendTailwindMerge`.
     * Without that the loser of each pair survives and stylesheet order,
     * rather than the caller, picks the winner.
     */
    describe("the project's custom scales", () => {
      const pairs: [scale: string, stock: string, token: string][] = [
        ["radius", "rounded-lg", "rounded-card"],
        ["elevation", "shadow-md", "shadow-2"],
        ["duration", "duration-300", "duration-fast"],
        ["easing", "ease-in", "ease-standard"],
      ];

      it.each(pairs)("merges the %s scale", (_scale, stock, token) => {
        expect(cn(stock, token)).toBe(token);
        // Position is the only thing that decides, in both directions.
        expect(cn(token, stock)).toBe(stock);
      });

      it("merges two token values of the same scale against each other", () => {
        expect(cn("rounded-ctl", "rounded-panel")).toBe("rounded-panel");
        expect(cn("shadow-1", "shadow-3")).toBe("shadow-3");
        expect(cn("duration-slow", "duration-fast")).toBe("duration-fast");
        expect(cn("ease-exit", "ease-emphasized")).toBe("ease-emphasized");
      });

      it("still merges the stock keys the scales were extended from", () => {
        // Extending a group must not replace it. Every class here is one the
        // app already ships, so the assertion costs no extra generated CSS --
        // Tailwind's content glob scans this file too.
        expect(cn("rounded-lg", "rounded-full")).toBe("rounded-full");
        expect(cn("shadow-sm", "shadow-lg")).toBe("shadow-lg");
        expect(cn("duration-300", "duration-200")).toBe("duration-200");
        expect(cn("ease-in", "ease-out")).toBe("ease-out");
      });

      it("keeps the four scales independent of one another", () => {
        expect(cn("rounded-card shadow-2 duration-fast ease-standard")).toBe(
          "rounded-card shadow-2 duration-fast ease-standard",
        );
      });
    });

    it("leaves non-conflicting utilities from both sides alone", () => {
      expect(cn("text-fg shadow-1", "bg-surface")).toBe(
        "text-fg shadow-1 bg-surface",
      );
    });

    it("does not mistake a shadow colour for a shadow size", () => {
      // `shadow-2` is an elevation; `shadow-primary` tints the shadow. They
      // are separate groups, and extending one must not swallow the other.
      expect(cn("shadow-2", "shadow-primary")).toBe("shadow-2 shadow-primary");
    });

    it("treats a variant as its own scope", () => {
      // `hover:bg-*` does not conflict with an unprefixed `bg-*`.
      expect(cn("bg-surface", "hover:bg-surface-muted")).toBe(
        "bg-surface hover:bg-surface-muted",
      );
    });
  });
});
