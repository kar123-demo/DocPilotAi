const LABELS = { frontend: "Frontend", backend: "Backend", database: "Database", tools: "Tools/Libraries" };

export default function TechStack({ stack }) {
  if (!stack) return null;
  return (
    <div className="stack-grid">
      {Object.entries(LABELS).map(([key, label]) => (
        <article key={key} className="stack-card">
          <h4>{label}</h4>
          <ul>
            {(stack[key] || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
