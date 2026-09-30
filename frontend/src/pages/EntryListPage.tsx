import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router";
import { fetchEntries } from "../api/entries";

function EntryListPage() {
  const {
    data: entries,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["entries"],
    queryFn: fetchEntries,
    enabled: Boolean(localStorage.getItem("access_token")),
  });

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;

  if (isLoading) {
    return <p role="status">불러오는 중...</p>;
  }

  if (error) {
    return <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>다시 시도</button></>;
  }

  return (
    <>
      <h2>Entries</h2>
      <Link to="/entries/new">새 노트 작성</Link>

      {entries?.length === 0 && <p>저장된 Entry가 없어.</p>}

      {entries?.map((entry) => (
        <article key={entry.id}>
          <Link to={`/entries/${entry.id}`}>
            <h3>{entry.title}</h3>
          </Link>
          <p>{entry.type}</p>
          <p className="entry-content">{entry.content ?? "내용 없음"}</p>
        </article>
      ))}
    </>
  );
}

export default EntryListPage;
