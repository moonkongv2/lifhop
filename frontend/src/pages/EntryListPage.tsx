import { useQuery } from "@tanstack/react-query";
import type { components } from "../api/generated/schema";
import { Link } from "react-router";

type Entry = components["schemas"]["EntryResponse"];

async function fetchEntries(): Promise<Entry[]> {
  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("로그인이 필요해.");
  }

  const response = await fetch("/api/entries", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Entry 조회 실패: ${response.status}`);
  }

  return response.json();
}

function EntryListPage() {
  const {
    data: entries,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["entries"],
    queryFn: fetchEntries,
  });

  if (isLoading) {
    return <p>불러오는 중...</p>;
  }

  if (error) {
    return <p>{error.message}</p>;
  }

  return (
    <>
      <h2>Entries</h2>

      {entries?.length === 0 && <p>저장된 Entry가 없어.</p>}

      {entries?.map((entry) => (
        <article key={entry.id}>
          <Link to={`/entries/${entry.id}`}>
            <h3>{entry.title}</h3>
          </Link>
          <p>{entry.type}</p>
          <p>{entry.content ?? "내용 없음"}</p>
        </article>
      ))}
    </>
  );
}

export default EntryListPage;
