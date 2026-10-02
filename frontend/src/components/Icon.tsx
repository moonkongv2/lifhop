type IconName = "archive" | "search" | "import" | "sources" | "note" | "arrow" | "history" | "more";
const paths: Record<IconName, string> = {
  archive: "M4 4h16v4H4z M6 8v12h12V8 M10 12h4",
  search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  import: "M12 3v12 M7 8l5-5 5 5 M4 14v6h16v-6",
  sources: "M8 6h12 M8 12h12 M8 18h12 M3 6h1 M3 12h1 M3 18h1",
  note: "M14 2H5v20h14V7z M14 2v5h5 M8 12h8 M8 16h6",
  arrow: "M19 12H5 M11 6l-6 6 6 6",
  history: "M3 12a9 9 0 1 0 3-7 M3 3v6h6 M12 7v5l3 2",
  more: "M5 12h.01 M12 12h.01 M19 12h.01",
};
export default function Icon({ name }: { name: IconName }) {
  return <svg className="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
