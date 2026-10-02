import { useState } from "react";
import type { FormEvent } from "react";
import type { Entry, EntryCreate } from "../api/entries";

type Props = {
  entry?: Entry;
  pending: boolean;
  error: Error | null;
  onSubmit: (data: EntryCreate) => void;
  onCancel: () => void;
};

function EntryForm({ entry, pending, error, onSubmit, onCancel }: Props) {
  const [title, setTitle] = useState(entry?.title ?? "");
  const [content, setContent] = useState(entry?.content ?? "");
  const [validation, setValidation] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!title.trim() || title.length > 255) {
      setValidation("Title must contain non-whitespace text and be no longer than 255 characters.");
      return;
    }
    setValidation("");
    onSubmit({ type: entry?.type ?? "NOTE", title, content });
  }

  return (
    <form noValidate onSubmit={handleSubmit}>
      <fieldset disabled={pending}>
        <label htmlFor="entry-title">Title</label>
        <input id="entry-title" value={title} maxLength={255} required
          onChange={(event) => setTitle(event.target.value)} />
        <label htmlFor="entry-content">Content</label>
        <textarea id="entry-content" rows={12} value={content}
          onChange={(event) => setContent(event.target.value)} />
        <div className="actions">
          <button className="primary" type="submit">{pending ? "Saving..." : "Save"}</button>
          <button type="button" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
      {(validation || error) && <p role="alert">{validation || error?.message}</p>}
    </form>
  );
}

export default EntryForm;
