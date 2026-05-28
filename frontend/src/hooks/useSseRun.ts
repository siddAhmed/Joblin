import { useEffect, useState } from "react";

export interface SseEvent {
  type: string;
  data: Record<string, unknown>;
}

export function useSseRun(runId: number | null) {
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setDone(false);

    const es = new EventSource(`/api/runs/${runId}/stream`);

    const handleMessage = (e: MessageEvent, type: string) => {
      const data = JSON.parse(e.data || "{}");
      setEvents((prev) => [...prev, { type, data }]);
      if (type === "run_done") {
        setDone(true);
        es.close();
      }
    };

    ["run_started", "company_scraping", "company_done", "company_failed", "discord_posted", "run_done"].forEach(
      (eventType) => {
        es.addEventListener(eventType, (e) => handleMessage(e as MessageEvent, eventType));
      }
    );

    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  return { events, done };
}
