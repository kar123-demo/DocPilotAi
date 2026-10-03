import { useEffect, useState } from "react";

export default function SectionNav({ sections }) {
  const [activeId, setActiveId] = useState(sections[0]?.id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActiveId(entry.target.id);
        });
      },
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 },
    );
    sections.forEach(({ id }) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav className="section-nav" aria-label="Report table of contents">
      <p className="nav-label">Contents</p>
      <ol>
        {sections.map((section, index) => (
          <li key={section.id}>
            <a href={`#${section.id}`} className={activeId === section.id ? "active" : ""}>
              <span className="nav-index">{String(index + 1).padStart(2, "0")}</span>
              {section.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
