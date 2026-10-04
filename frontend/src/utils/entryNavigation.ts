const filterKeys = ["q", "source", "source_state", "type", "date_field", "date_from", "date_to", "include_work_commentary"];
const conditionKeys = filterKeys.filter(key => !["date_field", "include_work_commentary"].includes(key));
export type EntryListContext = { pathname: "/entries" | "/search"; search: string };

export function hasLegacyFilters(params: URLSearchParams) {
  return filterKeys.some(key => params.has(key));
}

export function listParams(params: URLSearchParams, pathname: EntryListContext["pathname"]) {
  const result = new URLSearchParams();
  for (const key of pathname === "/search" ? [...filterKeys, "offset"] : ["offset"]) {
    const value = params.get(key)?.trim();
    if (value) result.set(key, value);
  }
  return result;
}

export function hasSearchConditions(params: URLSearchParams) {
  return conditionKeys.some(key => params.get(key)?.trim());
}

export function validPage(params: URLSearchParams) {
  const value = params.get("offset");
  return value === null || (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)));
}

export function listTarget(context: EntryListContext) {
  return context.pathname + (context.search ? `?${context.search}` : "");
}

export function listContext(pathname: EntryListContext["pathname"], params: URLSearchParams): EntryListContext {
  return { pathname, search: listParams(params, pathname).toString() };
}

export function resolveEntryContext(search: string, state?: unknown): EntryListContext {
  const params = new URLSearchParams(search);
  if (params.has("returnTo")) {
    const target = params.get("returnTo")!;
    if (target.startsWith("/") && !target.startsWith("//")) {
      try {
        const base = "https://lifhop.invalid";
        const url = new URL(target, base);
        if (url.origin === base && (url.pathname === "/entries" || url.pathname === "/search")) {
          const pathname = url.pathname === "/entries" && hasLegacyFilters(url.searchParams) ? "/search" : url.pathname;
          return listContext(pathname, url.searchParams);
        }
      } catch { /* Invalid destinations return to Entries. */ }
    }
    return { pathname: "/entries", search: "" };
  }
  if (state && typeof state === "object" && "entryListSearch" in state && typeof state.entryListSearch === "string") {
    const legacy = new URLSearchParams(state.entryListSearch);
    return listContext(hasLegacyFilters(legacy) ? "/search" : "/entries", legacy);
  }
  return { pathname: "/entries", search: "" };
}

export function entryTarget(id: number | "new", context: EntryListContext) {
  return `/entries/${id}?${new URLSearchParams({ returnTo: listTarget(context) })}`;
}
