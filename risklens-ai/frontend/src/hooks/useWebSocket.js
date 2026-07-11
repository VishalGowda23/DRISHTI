/**
 * RiskLens AI — WebSocket Hook
 * Custom React hook for real-time alert streaming.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export function useWebSocket() {
  const [alerts, setAlerts] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(`${WS_URL}/ws/alerts`);

      ws.onopen = () => {
        setIsConnected(true);
        console.log('🔌 WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'alert') {
            setAlerts((prev) => [message.data, ...prev].slice(0, 50));
          } else if (message.type === 'assessment') {
            setAssessments((prev) => [message.data, ...prev].slice(0, 20));
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('🔌 WebSocket disconnected, reconnecting in 3s...');
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        ws.close();
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      reconnectTimer.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const clearAlerts = () => setAlerts([]);

  return { alerts, assessments, isConnected, clearAlerts };
}
