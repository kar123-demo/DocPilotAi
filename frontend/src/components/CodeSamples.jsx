export default function CodeSamples({ samples }) {
  if (!samples || samples.length === 0) {
    return <p className="empty-note">No retrieval chunks were indexed for this repository.</p>;
  }
  return (
    <div className="code-samples">
      {samples.map((sample) => (
        <article key={`${sample.file}:${sample.start_line}`} className="code-sample">
          <header>
            <span className="code-file">{sample.file}</span>
            <span className="code-lines">
              lines {sample.start_line}–{sample.end_line} · {sample.language}
            </span>
          </header>
          <pre>
            <code>{sample.content}</code>
          </pre>
        </article>
      ))}
    </div>
  );
}
