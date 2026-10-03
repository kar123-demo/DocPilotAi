export default function TitlePage({ titlePage }) {
  if (!titlePage) return null;
  return (
    <div className="title-page">
      <h3>{titlePage.project_name}</h3>
      <dl>
        <div>
          <dt>Repository</dt>
          <dd className="mono">{titlePage.repository_url}</dd>
        </div>
      </dl>
    </div>
  );
}
