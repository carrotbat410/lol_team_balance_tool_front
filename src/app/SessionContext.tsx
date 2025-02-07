"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface User {
  id: number;
  email: string;
  name: string;
}

interface SessionContextType {
  user: User | null;
  setUser: (user: User | null) => void;
}

// 기본값을 null로 설정
const SessionContext = createContext<SessionContextType | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetch("http://localhost:8080/api/session", {
      credentials: "include", //모든 요청에 인증 정보를 포함 (e.g. 세션 쿠키)
    })
      .then((res) => res.json())
      .then((data) => setUser(data.user))
      .catch(() => setUser(null));
  }, []);

  return <SessionContext.Provider value={{ user, setUser }}>{children}</SessionContext.Provider>;
}

// useSession()의 타입을 명확하게 정의
export function useSession(): SessionContextType {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}