import ArtifactLinks from "./ArtifactLinks.jsx";

export default function DocumentActions({ artifacts, downloadUrl, onBack, onSaveProject, projectSaved, savingProject }) {
  return (
    <>
      <div className="document-actions">
        <button type="button" className="text-button" onClick={onBack}>
          ← New analysis
        </button>
        <div className="document-actions-right">
          <button type="button" className="outline-button" onClick={onSaveProject} disabled={projectSaved || savingProject}>
            {projectSaved ? "Project saved" : savingProject ? "Saving…" : "Save Project"}
          </button>
          <ArtifactLinks artifacts={artifacts} downloadUrl={downloadUrl} />
        </div>
      </div>
    </>
  );
}
