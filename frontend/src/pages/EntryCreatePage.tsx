import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate, useLocation } from "react-router";
import { createEntry } from "../api/entries";
import EntryForm from "../components/EntryForm";
import { entryTarget, listTarget, resolveEntryContext } from "../utils/entryNavigation";

function EntryCreatePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const context = resolveEntryContext(location.search, location.state);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createEntry,
    onSuccess: async (entry) => {
      queryClient.setQueryData(["entry", String(entry.id)], entry);
      await queryClient.invalidateQueries({ queryKey: ["entries"] });
      navigate(entryTarget(entry.id, context));
    },
  });

  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;

  return (
    <section className="panel page-card form-page">
      <p className="eyebrow">Capture a thought</p>
      <h2>New note</h2>
      <EntryForm pending={mutation.isPending} error={mutation.error}
        onSubmit={(data) => mutation.mutate(data)} onCancel={() => navigate(listTarget(context))} />
    </section>
  );
}

export default EntryCreatePage;
