import { useMutation } from "@tanstack/react-query";
import { fetchArtifactDownload } from "../api/imports";

function ArtifactDownload({ artifactId }: { artifactId: number }) {
  const mutation = useMutation({ mutationFn: () => fetchArtifactDownload(artifactId) });
  return (
    <div>
      <button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? "다운로드 준비 중..." : "원본 다운로드 준비"}
      </button>
      {mutation.data && <p><a href={mutation.data.download_url} target="_blank" rel="noreferrer">원본 파일 다운로드</a> (10분 동안 유효)</p>}
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
    </div>
  );
}
export default ArtifactDownload;
