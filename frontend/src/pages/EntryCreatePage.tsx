import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router";
import { createEntry } from "../api/entries";
import EntryForm from "../components/EntryForm";

function EntryCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createEntry,
    onSuccess: async (entry) => {
      queryClient.setQueryData(["entry", String(entry.id)], entry);
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      navigate(`/entries/${entry.id}`);
    },
  });

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;

  return (
    <>
      <h2>새 노트</h2>
      <EntryForm pending={mutation.isPending} error={mutation.error}
        onSubmit={(data) => mutation.mutate(data)} onCancel={() => navigate("/entries")} />
    </>
  );
}

export default EntryCreatePage;
