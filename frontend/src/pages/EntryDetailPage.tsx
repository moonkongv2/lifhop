import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useParams } from "react-router";

import type { components } from "../api/generated/schema";

type Entry = components["schemas"]["EntryResponse"];

async function fetchEntry(id: string): Promise<Entry> {
  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("로그인이 필요해.");
  }

  const response = await fetch(`/api/entries/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Entry 조회 실패: ${response.status}`);
  }

  return response.json();
}

function EntryDetailPage() {
  const { id } = useParams();
  const token = localStorage.getItem("access_token");

  const {
    data: entry,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["entry", id],
    queryFn: () => fetchEntry(id!),
    enabled: Boolean(token && id),
  });

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (!id) {
    return <p>Entry ID가 없어.</p>;
  }

  if (isLoading) {
    return <p>불러오는 중...</p>;
  }

  if (error) {
    return <p>{error.message}</p>;
  }

  if (!entry) {
    return <p>Entry를 찾을 수 없어.</p>;
  }

  return (
    <>
      <Link to="/entries">← 목록으로</Link>

      <h2>{entry.title}</h2>

      <p>Type: {entry.type}</p>
      <p>{entry.content ?? "내용 없음"}</p>

      {entry.event_at && (
        <p>Event at: {new Date(entry.event_at).toLocaleString()}</p>
      )}

      <p>Created: {new Date(entry.created_at).toLocaleString()}</p>
      <p>Updated: {new Date(entry.updated_at).toLocaleString()}</p>
    </>
  );
}

export default EntryDetailPage;
