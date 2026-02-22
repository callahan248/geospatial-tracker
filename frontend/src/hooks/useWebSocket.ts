import { useEffect, useRef, useState } from "react";

export type WsMessage = {
  type: "aircraft" | "detections" | "error";
  data?: unknown;
  message?: string;
  source?: string;
};

/**
 * Connects to the backend WebSocket and returns the latest parsed message.
 * Automatically reconnects on disconnect.
 */
export function useWebSocket(url: string): WsMessage | null {
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data as string);
          setLastMessage(msg);
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [url]);

  return lastMessage;
}
