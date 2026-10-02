import { useQuery } from "@tanstack/react-query";
import { fetchEntrySearch } from "../api/entries";
import { validPage } from "../utils/entryNavigation";

export default function useEntrySearch(params: URLSearchParams, enabled = true) {
  const serialized = params.toString();
  const validOffset = validPage(params);
  const query = useQuery({
    queryKey: ["entries", serialized],
    queryFn: ({ signal }) => fetchEntrySearch(new URLSearchParams(serialized), signal),
    enabled: Boolean(localStorage.getItem("access_token") && enabled && validOffset),
  });
  return { ...query, offset: Number(params.get("offset") ?? 0), validOffset };
}
