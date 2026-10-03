export default function DatabaseDesign({ database }) {
  if (!database) return null;
  return (
    <div className="db-block">
      <h4>Detected technology</h4>
      <ul>
        {database.detected_technology.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="muted-note">{database.note}</p>
      {database.model_like_classes && database.model_like_classes.length > 0 ? (
        <ul className="pill-list">
          {database.model_like_classes.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
