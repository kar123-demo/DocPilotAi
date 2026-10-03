export default function TestingSection({ testing }) {
  if (!testing) return null;
  return (
    <div className="testing-block">
      <p className="muted-note">{testing.note}</p>
      <p>
        <strong>Frameworks detected:</strong> {testing.frameworks_detected.join(", ")}
      </p>
      {testing.test_files.length > 0 ? (
        <ul>
          {testing.test_files.map((file) => (
            <li key={file}>{file}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
