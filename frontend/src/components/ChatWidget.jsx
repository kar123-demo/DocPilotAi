import { useEffect, useRef, useState } from "react";
import { askRepository } from "../api.js";

const SUGGESTIONS = [
  "Where does the application start?",
  "Which files handle the main user workflow?",
  "Explain the code that processes an API request.",
];

export default function ChatWidget({ reportId, projectName, standalone = false }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [popupError, setPopupError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    setMessages([]);
  }, [reportId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    if (standalone) document.title = `${projectName} Chat — DocPilot AI`;
  }, [standalone, projectName]);

  if (!reportId) return null;

  const openSeparateWindow = () => {
    const chatUrl = new URL(window.location.href);
    chatUrl.searchParams.set("chatProject", reportId);
    chatUrl.searchParams.set("projectName", projectName);
    const popup = window.open(
      chatUrl.toString(),
      `docpilot-chat-${reportId}`,
      "popup,width=520,height=760,resizable=yes,scrollbars=yes",
    );
    if (popup) {
      popup.focus();
      setPopupError("");
    } else {
      setPopupError("Your browser blocked the chat window. Allow pop-ups for this site and try again.");
    }
  };

  const ask = async (asked) => {
    const text = asked.trim();
    if (!text || loading) return;
    setQuestion("");
    setLoading(true);
    try {
      const history = messages
        .filter((message) => !message.error && message.answer)
        .slice(-4)
        .flatMap((message) => [
          { role: "user", content: message.question },
          { role: "assistant", content: message.answer },
        ]);
      const payload = await askRepository(reportId, { question: text, history });
      setMessages((current) => [...current, { question: text, ...payload }]);
    } catch (err) {
      setMessages((current) => [...current, { question: text, error: err.message }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    ask(question);
  };

  return (
    <div className={standalone ? "chat-standalone" : "chat-widget"}>
      {!standalone ? (
        <>
          <button type="button" className="chat-launcher" onClick={openSeparateWindow}>
            Open project chat <span aria-hidden="true">↗</span>
          </button>
          {popupError ? <p className="chat-popup-error" role="alert">{popupError}</p> : null}
        </>
      ) : (
        <div className="chat-window chat-window-standalone">
          <header>
            <div className="chat-window-heading">
              <span className="eyebrow">Repository assistant</span>
              <strong>{projectName}</strong>
              <span>Answers grounded in indexed source files</span>
            </div>
            <button type="button" className="chat-close" onClick={() => window.close()} aria-label="Close chat window">
              ×
            </button>
          </header>

          <div className="chat-messages" ref={scrollRef}>
            {messages.length === 0 ? (
              <div className="chat-empty">
                <p>Ask about files, functions, architecture, or behavior in this codebase.</p>
                <div className="chat-suggestions">
                  {SUGGESTIONS.map((item) => (
                    <button key={item} type="button" onClick={() => ask(item)}>
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <div className="chat-turn" key={index}>
                  <p className="chat-question">{message.question}</p>
                  {message.error ? (
                    <p className="chat-error">{message.error}</p>
                  ) : (
                    <div className="chat-answer">
                      <p style={{ whiteSpace: "pre-wrap" }}>{message.answer}</p>
                      {!message.llm_used && message.llm_status ? (
                        <p className="chat-error">{message.llm_status}</p>
                      ) : null}
                      <small>
                        {message.sync_status}. Code sources:{" "}
                        {message.sources?.length
                          ? message.sources.map((source) => `${source.file}:${source.lines}`).join(", ")
                          : "No indexed source matched"}
                      </small>
                    </div>
                  )}
                </div>
              ))
            )}
            {loading ? <p className="chat-pending">Thinking…</p> : null}
          </div>

          <form onSubmit={handleSubmit}>
            <input
              required
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about this repository’s source code…"
            />
            <button type="submit" disabled={loading}>
              {loading ? "…" : "Ask"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
