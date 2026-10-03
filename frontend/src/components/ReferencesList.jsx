export default function ReferencesList({ references }) {
  if (!references || references.length === 0) return null;
  return (
    <ol className="references-list">
      {references.map((reference) => (
        <li key={reference.url}>
          <a href={reference.url} target="_blank" rel="noreferrer">
            {reference.title}
          </a>
          <p>{reference.description}</p>
          <span className="reference-url">{reference.url}</span>
        </li>
      ))}
    </ol>
  );
}
