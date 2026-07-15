"use client";
import Link from 'next/link';
import Image from 'next/image';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { clearAuthState, isStoredLoginActive } from '../utils/auth';

export default function NavbarRight() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const router = useRouter();
  
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsLoggedIn(isStoredLoginActive());
    }

    const syncLoginState = () => {
      setIsLoggedIn(isStoredLoginActive());
    };

    window.addEventListener('storage', syncLoginState);
    window.addEventListener('auth-change', syncLoginState);

    return () => {
      window.removeEventListener('storage', syncLoginState);
      window.removeEventListener('auth-change', syncLoginState);
    };
  }, []);

  const handleLogout = () => {
    clearAuthState();
    localStorage.removeItem('team1List');
    localStorage.removeItem('team2List');
    localStorage.removeItem('noTeamList');
    window.dispatchEvent(new Event('auth-change'));
    router.push('/');
  };

  if (isLoggedIn) {
    return (
      <>
        <Link href="/my-account" className="user-icon-btn">
          <Image src="/user-icon.png" alt="유저 아이콘" width={36} height={36} />
        </Link>
        <button className="logout-btn" onClick={handleLogout}>로그아웃</button>
      </>
    );
  }
  return (
    <Link href="/login" className="login-btn">로그인</Link>
  );
}
