const LABELS = {
  readme: "README.md",
  api_reference: "API_REFERENCE.md",
  architecture: "ARCHITECTURE.md",
};

export default function ArtifactLinks({ artifacts = {}, downloadUrl }) {
  return (
    <div className="artifact-links">
      {downloadUrl ? (
        <a className="primary-button" href={downloadUrl}>
          Download DOCX
        </a>
      ) : null}
      {Object.entries(artifacts).map(([name, url]) => (
        <a key={name} className="outline-button artifact-link" href={url} target="_blank" rel="noreferrer">
          {LABELS[name] || name}
        </a>
      ))}
    </div>
  );
}
