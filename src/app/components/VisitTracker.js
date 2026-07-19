"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import API_BASE_URL from "../utils/api";
import { getAuthToken } from "../utils/auth";

const VISITOR_ID_KEY = "lolCivilWarVisitorId";

const createVisitorId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

const getOrCreateVisitorId = () => {
  const storedVisitorId = localStorage.getItem(VISITOR_ID_KEY);
  if (storedVisitorId) {
    return storedVisitorId;
  }

  const visitorId = createVisitorId();
  localStorage.setItem(VISITOR_ID_KEY, visitorId);
  return visitorId;
};

export default function VisitTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (!API_BASE_URL || !pathname) {
      return;
    }

    const controller = new AbortController();
    const visitorId = getOrCreateVisitorId();
    const token = getAuthToken();

    fetch(`${API_BASE_URL}/visits`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        visitorId,
        path: pathname,
      }),
      keepalive: true,
      signal: controller.signal,
    }).catch(() => {
      // 방문자 집계 실패가 사용자의 화면 이용을 막으면 안 됩니다.
    });

    return () => {
      controller.abort();
    };
  }, [pathname]);

  return null;
}
