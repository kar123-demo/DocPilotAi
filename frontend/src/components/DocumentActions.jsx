import { useEffect, useState } from "react";
import ArtifactLinks from "./ArtifactLinks.jsx";

export default function DocumentActions({ artifacts, downloadUrl, onBack, sections }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selected, setSelected] = useState(() =>
    Object.fromEntries(sections.map((section) => [section.id, true])),
  );
  const selectedCount = sections.filter((section) => selected[section.id]).length;

  useEffect(() => {
    const clearPrintSelection = () => {
      document.querySelectorAll("[data-pdf-excluded]").forEach((section) => {
        delete section.dataset.pdfExcluded;
      });
    };
    window.addEventListener("afterprint", clearPrintSelection);
    return () => window.removeEventListener("afterprint", clearPrintSelection);
  }, []);

  const toggleSection = (sectionId) => {
    setSelected((current) => ({ ...current, [sectionId]: !current[sectionId] }));
  };

  const toggleAll = () => {
    const selectAll = selectedCount !== sections.length;
    setSelected(Object.fromEntries(sections.map((section) => [section.id, selectAll])));
  };

  const printSelected = () => {
    document.querySelectorAll("[data-report-section]").forEach((section) => {
      section.dataset.pdfExcluded = String(!selected[section.dataset.reportSection]);
    });
    setPickerOpen(false);
    window.requestAnimationFrame(() => window.print());
  };

  return (
    <>
      <div className="document-actions">
        <button type="button" className="text-button" onClick={onBack}>
          ← New analysis
        </button>
        <div className="document-actions-right">
          <button type="button" className="outline-button" onClick={() => setPickerOpen(true)}>
            Print / Save PDF
          </button>
          <ArtifactLinks artifacts={artifacts} downloadUrl={downloadUrl} />
        </div>
      </div>
      {pickerOpen ? (
        <div className="pdf-picker-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setPickerOpen(false);
        }}>
          <section
            className="pdf-picker"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pdf-picker-title"
          >
            <button
              type="button"
              className="pdf-picker-close"
              aria-label="Close section selector"
              onClick={() => setPickerOpen(false)}
            >
              ×
            </button>
            <p className="eyebrow">PDF export</p>
            <h2 id="pdf-picker-title">Choose report sections</h2>
            <p className="pdf-picker-description">
              Select the sections to include, then choose “Save as PDF” in the print dialog.
            </p>
            <button type="button" className="pdf-select-all" onClick={toggleAll}>
              {selectedCount === sections.length ? "Clear selection" : "Select all sections"}
            </button>
            <div className="pdf-section-list">
              {sections.map((section) => (
                <label className="pdf-section-option" key={section.id}>
                  <input
                    type="checkbox"
                    checked={Boolean(selected[section.id])}
                    onChange={() => toggleSection(section.id)}
                  />
                  <span>{section.title}</span>
                </label>
              ))}
            </div>
            <div className="pdf-picker-actions">
              <button type="button" className="text-button" onClick={() => setPickerOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="generate-button"
                disabled={selectedCount === 0}
                onClick={printSelected}
              >
                Continue to print ({selectedCount})
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
