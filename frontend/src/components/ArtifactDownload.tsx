import { useMutation } from "@tanstack/react-query";
import { fetchArtifactDownload } from "../api/imports";

function ArtifactDownload({ artifactId }: { artifactId: number }) {
  const mutation = useMutation({ mutationFn: () => fetchArtifactDownload(artifactId) });
  return (
    <div className="original-download">
      <button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? "Preparing download..." : "Prepare original download"}
      </button>
      {mutation.data && <p><a href={mutation.data.download_url} target="_blank" rel="noreferrer">Download original file</a> (valid for 10 minutes)</p>}
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
    </div>
  );
}
export default ArtifactDownload;
