import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate, useLocation } from "react-router";
import { createEntry } from "../api/entries";
import EntryForm from "../components/EntryForm";

function EntryCreatePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const search = typeof location.state?.entryListSearch === "string" ? location.state.entryListSearch : "";
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createEntry,
    onSuccess: async (entry) => {
      queryClient.setQueryData(["entry", String(entry.id)], entry);
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      navigate(`/entries/${entry.id}`, { state: { entryListSearch: search } });
    },
  });

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;

  return (
    <>
      <h2>새 노트</h2>
      <EntryForm pending={mutation.isPending} error={mutation.error}
        onSubmit={(data) => mutation.mutate(data)} onCancel={() => navigate(search ? `/entries?${search}` : "/entries")} />
    </>
  );
}

export default EntryCreatePage;
