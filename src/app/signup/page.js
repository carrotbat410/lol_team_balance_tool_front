"use client";
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SignupPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const validateInput = (value) => {
    const regex = /^[a-zA-Z0-9]+$/;
    return regex.test(value) && value.length >= 6;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    
    if (!validateInput(username)) {
      setError("아이디는 영문, 숫자만 입력 가능하며 최소 6자 이상 입력해주세요.");
      return;
    }
    
    if (!validateInput(password)) {
      setError("비밀번호는 영문, 숫자만 입력 가능하며 최소 6자 이상 입력해주세요.");
      return;
    }
    
    if (password !== confirmPassword) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }

    try {
      const res = await fetch("http://localhost:8080/join", {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: username,
          password: password
        }),
      });
      if (res.status === 200) {
        router.push("/login");
      } else if (res.status === 409) {
        setError("이미 존재하는 아이디입니다.");
      } else {
        setError("회원가입 중 오류가 발생했습니다.");
      }
    } catch (err) {
      setError("서버와 연결할 수 없습니다.");
    }
  };

  return (
    <div className="login-page container">
      <h1>회원가입</h1>
      <form className="login-form" onSubmit={handleSubmit}>
        <label htmlFor="username">아이디</label>
        <input 
          id="username" 
          name="username" 
          type="text" 
          autoComplete="username" 
          required 
          value={username} 
          onChange={e => setUsername(e.target.value)} 
        />
        <div className="input-hint">영문, 숫자만 입력 가능. 최소 6자 이상 입력하세요</div>
        <label htmlFor="password">비밀번호</label>
        <input 
          id="password" 
          name="password" 
          type="password" 
          autoComplete="new-password" 
          required 
          value={password} 
          onChange={e => setPassword(e.target.value)} 
        />
        <div className="input-hint">영문, 숫자만 입력 가능. 최소 6자 이상 입력하세요</div>
        <label htmlFor="confirmPassword">비밀번호 확인</label>
        <input 
          id="confirmPassword" 
          name="confirmPassword" 
          type="password" 
          autoComplete="new-password" 
          required 
          value={confirmPassword} 
          onChange={e => setConfirmPassword(e.target.value)} 
        />
        {error && <div className="login-error">{error}</div>}
        <button type="submit">회원가입</button>
      </form>
    </div>
  );
} 