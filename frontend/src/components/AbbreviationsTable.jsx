export default function AbbreviationsTable({ abbreviations }) {
  if (!abbreviations || abbreviations.length === 0) return null;
  return (
    <dl className="abbreviations-list">
      {abbreviations.map((entry) => (
        <div key={entry.term} className="abbreviation-row">
          <dt>{entry.term}</dt>
          <dd>{entry.definition}</dd>
        </div>
      ))}
    </dl>
  );
}
