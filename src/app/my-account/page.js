'use client';
import { useState, useEffect } from 'react';

export default function MyAccountPage() {
  const [username, setUsername] = useState('');

  useEffect(() => {
    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      setUsername(storedUsername);
    }
  }, []);

  return (
    <div className="my-account-page">
      <h1>내 정보</h1>
      <div className="account-info-card">
        <div className="info-item">
          <span className="info-label">닉네임</span>
          <span className="info-value">{username}</span>
        </div>
        <div className="info-item">
          <span className="info-label">비밀번호</span>
          <button className="change-password-btn" onClick={() => alert('현재 개발중인 기능입니다.')}>비밀번호 변경</button>
        </div>
      </div>
      <div className="account-actions">
        <button className="delete-account-btn" onClick={() => alert('현재 개발중인 기능입니다.')}>회원 탈퇴</button>
      </div>
    </div>
  );
}