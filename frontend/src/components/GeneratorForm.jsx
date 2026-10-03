export default function GeneratorForm({ form, onChange, onSubmit, busy, aiReady, llmHint, models, error }) {
  const update = (event) => onChange(event.target.name, event.target.value);

  return (
    <form className="generator-form" onSubmit={onSubmit} id="generate">
      <div className="form-head">
        <p className="eyebrow">Connect a repository</p>
        <h2>Generate living documentation</h2>
        <p className="muted">
          Start with a public GitHub repository. We’ll map its code, build searchable project context, and create
          documentation grounded in the source.
        </p>
      </div>

      <label className="field-span">
        Public GitHub repository URL
        <input
          required
          type="url"
          name="repository_url"
          value={form.repository_url}
          onChange={update}
          placeholder="https://github.com/owner/project"
          autoComplete="off"
        />
      </label>

      <div className="form-grid">
        <label>
          Project name
          <input
            name="project_name"
            value={form.project_name}
            onChange={update}
            placeholder="Auto-detected from repository"
          />
        </label>
      </div>

      <div className="form-actions">
        <button className="generate-button" disabled={busy} type="submit">
          {busy ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              Analyzing repository…
            </>
          ) : (
            <>Generate complete documentation</>
          )}
        </button>
        <p className="hint">
          {aiReady
            ? `Groq models — report quality: ${models?.quality || "configured"}; report fast: ${models?.fast || "configured"}; UML: ${models?.uml || "configured"}; source chat: ${models?.chat || "configured"}.`
            : llmHint || "Configure GROQ_API_KEY in the backend environment. Static analysis remains available without it."}
        </p>
      </div>
      {error ? <p className="error-message">{error}</p> : null}
    </form>
  );
}
