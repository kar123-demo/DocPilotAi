/** A numbered section, matching the same table-of-contents order used in the generated DOCX. */
export default function Section({ id, number, title, note, children }) {
  return (
    <section id={id} className="report-section">
      <div className="section-heading">
        <span className="section-number">{number}</span>
        <div>
          <h2>{title}</h2>
          {note ? <p className="section-note">{note}</p> : null}
        </div>
      </div>
      <div className="section-body">{children}</div>
    </section>
  );
}
