import { describe, expect, it } from "vitest";
import { entryTarget, hasSearchConditions, listTarget, resolveEntryContext, validPage } from "./entryNavigation";

describe("Entry return destinations", () => {
  it("preserves query and page without history state", () => {
    const target = entryTarget(7, { pathname: "/search", search: "q=120+RPM&source=manual&offset=20" });
    const context = resolveEntryContext(new URL(target, "https://local.invalid").search);
    expect(listTarget(context)).toBe("/search?q=120+RPM&source=manual&offset=20");
    expect(target).not.toContain("returnTo%3D");
  });
  it.each(["https://evil.example/search", "//evil.example/search", "/\\evil.example/search", "/login", "/search/extra", "broken", "/%2Fsearch"])("falls back for %s", returnTo => {
    expect(listTarget(resolveEntryContext(`?${new URLSearchParams({ returnTo })}`, { entryListSearch: "q=old" }))).toBe("/entries");
  });
  it("keeps only known parameters and removes nested return destinations", () => {
    const context = resolveEntryContext(`?${new URLSearchParams({ returnTo: "/search?q=worker&limit=100&returnTo=https://evil.example&offset=20" })}`);
    expect(listTarget(context)).toBe("/search?q=worker&offset=20");
  });
  it("supports old list context, including page-only Entries and filtered old URLs", () => {
    expect(listTarget(resolveEntryContext("", { entryListSearch: "offset=20" }))).toBe("/entries?offset=20");
    expect(listTarget(resolveEntryContext("", { entryListSearch: "q=worker&offset=20" }))).toBe("/search?q=worker&offset=20");
    expect(listTarget(resolveEntryContext(`?${new URLSearchParams({ returnTo: "/entries?q=worker&offset=20" })}`))).toBe("/search?q=worker&offset=20");
    expect(listTarget(resolveEntryContext(""))).toBe("/entries");
  });
  it("distinguishes filters from blank queries and pagination", () => {
    expect(hasSearchConditions(new URLSearchParams("date_field=event_at&offset=20&q=+"))).toBe(false);
    expect(hasSearchConditions(new URLSearchParams("source=manual"))).toBe(true);
  });
  it.each(["-1", "1.5", "0x20", "oops", "9007199254740992"])("rejects invalid offsets %s", offset => {
    expect(validPage(new URLSearchParams({ offset }))).toBe(false);
  });
});
