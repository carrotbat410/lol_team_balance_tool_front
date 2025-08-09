"use client";
import Link from 'next/link';
import Image from 'next/image';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function NavbarRight() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const router = useRouter();
  
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsLoggedIn(localStorage.getItem('isLoggedIn') === 'true');
    }
    const handleStorage = () => {
      setIsLoggedIn(localStorage.getItem('isLoggedIn') === 'true');
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('username');
    window.dispatchEvent(new Event('storage'));
    router.push('/');
  };

  if (isLoggedIn) {
    return (
      <>
        <Link href="/myAccountInfo" className="user-icon-btn">
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