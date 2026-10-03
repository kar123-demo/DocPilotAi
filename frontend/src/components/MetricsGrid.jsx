export default function MetricsGrid({ summary }) {
  if (!summary) return null;
  const languages = Array.isArray(summary.languages) ? summary.languages : [];
  const metrics = [
    { label: "Source files", value: summary.files ?? "—" },
    { label: "Functions", value: summary.functions ?? "—" },
    { label: "Classes", value: summary.classes ?? "—" },
    { label: "Languages", value: languages.join(", ") || "—" },
  ];
  const byLanguage = summary.files_by_language || {};

  return (
    <div className="metrics-grid">
      {metrics.map((metric) => (
        <article key={metric.label}>
          <b>{metric.value}</b>
          <span>{metric.label}</span>
        </article>
      ))}
      {Object.keys(byLanguage).length > 0 ? (
        <table className="language-table">
          <thead>
            <tr>
              <th>Language</th>
              <th>Source files</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(byLanguage).map(([language, count]) => (
              <tr key={language}>
                <td>{language}</td>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
