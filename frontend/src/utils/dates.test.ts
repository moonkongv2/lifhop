import { expect, it } from "vitest";
import { validDate, validLocalDateTime } from "./dates";

it("validates calendar dates rather than accepting normalized invalid days", () => {
  expect(validDate("2024-02-29")).toBe(true);
  for (const value of ["2025-02-29", "2026-04-31", "2026-13-01", "2026-1-2", "0000-01-01", "text"]) expect(validDate(value)).toBe(false);
});
it("requires a complete valid date and 24-hour local time", () => {
  expect(validLocalDateTime("2026-10-03T23:59")).toBe(true);
  for (const value of ["2026-02-31T10:00", "2026-10-03T24:00", "2026-10-03T12:60", "T12:00", "2026-10-03T"]) expect(validLocalDateTime(value)).toBe(false);
});
