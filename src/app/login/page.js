"use client";
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const formData = new FormData();
    formData.append("userId", username);
    formData.append("password", password);
    try {
      // * INFO `fetch` 함수의 `body`에 `FormData` 객체를 전달하면, 브라우저는 자동으로 `Content-Type` 헤더를 `multipart/form-data`로 설정함.
      // * `Content-Type`을 수동으로 설정하면 안 됨. 수동 설정시 form-data 의 boundary 가 누락되어 서버에서 파싱 불가해짐.
      const res = await fetch("http://localhost:8080/login", {
        method: "POST",
        body: formData,
      });
      if (res.status === 200) {
        const data = await res.json();
        document.cookie = `token=${data.token}; path=/;`;
        localStorage.setItem("username", data.username);
        localStorage.setItem("isLoggedIn", "true");
        window.dispatchEvent(new Event("storage"));
        router.push("/");
      } else if (res.status === 401) {
        setError("아이디 또는 비밀번호가 틀렸습니다.");
      } else {
        setError("알 수 없는 오류가 발생했습니다.");
      }
    } catch (err) {
      setError("서버와 연결할 수 없습니다.");
    }
  };

  return (
    <div className="login-page container">
      <h1>로그인</h1>
      <form className="login-form" onSubmit={handleSubmit}>
        <label htmlFor="username">아이디</label>
        <input id="username" name="username" type="text" autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} />
        <label htmlFor="password">비밀번호</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
        {error && <div className="login-error">{error}</div>}
        <button type="submit">로그인</button>
        <Link href="/signup" className="signup-link">회원가입</Link>
      </form>
    </div>
  );
} 