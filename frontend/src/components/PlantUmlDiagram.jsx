import { useState } from "react";

export default function PlantUmlDiagram({ code, imageUrl, title }) {
  const [showSource, setShowSource] = useState(false);

  return (
    <div className="diagram-block">
      <div className="diagram-toolbar">
        <span className="diagram-tag">{title}</span>
        {imageUrl ? (
          <button type="button" className="link-button" onClick={() => setShowSource((value) => !value)}>
            {showSource ? "Show rendered diagram" : "Show PlantUML source"}
          </button>
        ) : null}
      </div>
      {showSource || !imageUrl ? (
        <pre className="diagram-source">{code}</pre>
      ) : (
        <div className="diagram-canvas">
          <img className="diagram-image" src={imageUrl} alt={title} />
        </div>
      )}
    </div>
  );
}
