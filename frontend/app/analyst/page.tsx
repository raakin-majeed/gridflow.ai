"use client";

import { useState } from "react";
import { PageHeader } from "../components/page-header";
import { apiFetch } from "../utils/api";

type QaEntry = {
  question: string;
  answer: string;
};

const suggestedQuestions = [
  "Which state has highest risk tomorrow?",
  "Should I charge or discharge batteries tonight?",
  "Any critical anomalies to worry about?",
  "What is the demand forecast for Maharashtra this week?",
];

export default function AnalystPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<QaEntry[]>([]);

  const submit = async (value?: string) => {
    const query = (value ?? question).trim();
    if (!query) return;

    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch<{ answer?: string }>("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });
      const text =
        typeof payload.answer === "string" && payload.answer.trim().length > 0
          ? payload.answer
          : "No response received.";
      setAnswer(text);
      setHistory((prev) => [{ question: query, answer: text }, ...prev].slice(0, 5));
      setQuestion("");
    } catch {
      setError("CONNECTION ERROR — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI GRID ANALYST"
        subtitle="Powered by Groq LLaMA · Real-time grid context"
      />

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="h-[60px] w-full rounded border border-[#1a2a1a] bg-[#07080d] px-3 text-white"
            placeholder="Ask GRIDFLOW AI..."
          />
          <button
            className="rounded border border-[#1a2a1a] bg-[#00ff88] px-4 font-bold text-black"
            onClick={() => void submit()}
            disabled={loading}
          >
            QUERY
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {suggestedQuestions.map((item) => (
            <button
              key={item}
              className="rounded border border-[#1a2a1a] bg-[#07080d] px-3 py-1 text-xs text-[#cccccc]"
              onClick={() => {
                setQuestion(item);
                void submit(item);
              }}
              disabled={loading}
            >
              {item}
            </button>
          ))}
        </div>
      </section>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-[#00ff88]">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[#00ff88] border-t-transparent" />
          LOADING...
        </div>
      ) : null}
      {error ? <p className="text-sm text-[#ff4455]">{error}</p> : null}

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <p className="border-l-4 border-[#00ff88] pl-3 text-xs font-bold text-[#00ff88]">GRIDFLOW AI</p>
        <p className="mt-3 whitespace-pre-wrap text-sm text-white">
          {answer || "Query the analyst to generate a response."}
        </p>
      </section>

      <section className="space-y-3">
        <p className="text-sm text-[#cccccc]">Last 5 Q&A</p>
        {history.map((item, index) => (
          <details key={`${item.question}-${index}`} className="rounded border border-[#1a2a1a] bg-[#0d1117] p-3">
            <summary className="cursor-pointer text-sm text-[#cccccc]">{item.question}</summary>
            <p className="mt-2 text-sm text-white">{item.answer}</p>
          </details>
        ))}
      </section>
    </div>
  );
}
