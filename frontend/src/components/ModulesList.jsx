export default function ModulesList({ modules }) {
  if (!modules || modules.length === 0) return <p className="muted-note">No modules detected.</p>;
  return (
    <div className="modules-grid">
      {modules.map((module) => (
        <article key={module.name} className="module-card">
          <header>
            <span className="module-name">{module.name}/</span>
            <span className="module-meta">
              {module.file_count} file{module.file_count === 1 ? "" : "s"} · {module.languages.join(", ")}
            </span>
          </header>
          <ul>
            {module.files.map((file) => (
              <li key={file}>{file}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
