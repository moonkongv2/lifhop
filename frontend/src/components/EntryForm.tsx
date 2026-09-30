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
      setValidation("제목은 공백만으로 작성할 수 없고, 255자 이하여야 해.");
      return;
    }
    setValidation("");
    onSubmit({ type: entry?.type ?? "NOTE", title, content });
  }

  return (
    <form onSubmit={handleSubmit}>
      <fieldset disabled={pending}>
        <label htmlFor="entry-title">제목</label>
        <input id="entry-title" value={title} maxLength={255} required
          onChange={(event) => setTitle(event.target.value)} />
        <label htmlFor="entry-content">내용</label>
        <textarea id="entry-content" rows={12} value={content}
          onChange={(event) => setContent(event.target.value)} />
        <div className="actions">
          <button type="submit">{pending ? "저장 중..." : "저장"}</button>
          <button type="button" onClick={onCancel}>취소</button>
        </div>
      </fieldset>
      {(validation || error) && <p role="alert">{validation || error?.message}</p>}
    </form>
  );
}

export default EntryForm;
