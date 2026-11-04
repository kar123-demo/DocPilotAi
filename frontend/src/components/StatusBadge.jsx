export default function StatusBadge({ status }) {
  if (!status) {
    return (
      <div className="status-badge pending">
        <span className="status-dot" />
        Checking engine…
      </div>
    );
  }
  const ready = status.llm_configured ?? status.groq_configured;
  return (
    <div className={`status-badge ${ready ? "ready" : "missing"}`}>
      <span className="status-dot" />
      {ready ? "Model activated" : "Model not activated"}
    </div>
  );
}
