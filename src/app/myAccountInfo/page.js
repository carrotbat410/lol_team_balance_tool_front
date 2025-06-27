"use client";
import { useEffect, useState } from "react";

export default function MyAccountInfo() {
  const [username, setUsername] = useState("");
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setUsername(localStorage.getItem("username") || "");
    }
  }, []);

  return (
    <div className="container" style={{marginTop: '64px', textAlign: 'center'}}>
      <h1>내 계정 정보{username ? `: ${username}` : ""}</h1>
      <p>이곳은 임시 계정 정보 페이지입니다.</p>
    </div>
  );
} 