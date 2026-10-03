export default function BulletList({ items, heading }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="bullet-block">
      {heading ? <h4>{heading}</h4> : null}
      <ul className="bullet-list">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
