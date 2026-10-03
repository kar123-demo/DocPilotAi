async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(formatDetail(payload.detail) || `Request to ${path} failed (${response.status}).`);
  }
  return payload;
}

function formatDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || item.detail || (typeof item === "string" ? item : JSON.stringify(item)))
      .join(" ");
  }
  return String(detail);
}

export const getStatus = () => request("/api/status");

export const analyzeRepository = (body) =>
  request("/api/analyze", { method: "POST", body: JSON.stringify(body) });

export const askRepository = (projectId, body) =>
  request(`/api/projects/${projectId}/chat`, { method: "POST", body: JSON.stringify(body) });
