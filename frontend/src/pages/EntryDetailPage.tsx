import { useParams } from "react-router";

function EntryDetailPage() {
  const { id } = useParams();

  return (
    <>
      <h2>Entry Detail</h2>
      <p>Entry ID: {id}</p>
    </>
  );
}

export default EntryDetailPage;
