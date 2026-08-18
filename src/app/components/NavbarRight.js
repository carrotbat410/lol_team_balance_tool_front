"use client";
import Link from 'next/link';
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { clearAuthState, isStoredLoginActive } from '../utils/auth';
import { isOperator, ROLE_ADMIN } from '../community/permissions';

export default function NavbarRight() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [role, setRole] = useState('');
  const [isOperatorMenuOpen, setIsOperatorMenuOpen] = useState(false);
  const operatorMenuRef = useRef(null);
  const operatorButtonRef = useRef(null);
  const router = useRouter();
  
  useEffect(() => {
    const syncLoginState = () => {
      setIsLoggedIn(isStoredLoginActive());
      setRole(localStorage.getItem('role') || '');
      setIsOperatorMenuOpen(false);
    };

    syncLoginState();
    window.addEventListener('storage', syncLoginState);
    window.addEventListener('auth-change', syncLoginState);

    return () => {
      window.removeEventListener('storage', syncLoginState);
      window.removeEventListener('auth-change', syncLoginState);
    };
  }, []);

  useEffect(() => {
    if (!isOperatorMenuOpen) {
      return;
    }

    const handleOutsideClick = (event) => {
      if (!operatorMenuRef.current?.contains(event.target)) {
        setIsOperatorMenuOpen(false);
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsOperatorMenuOpen(false);
        operatorButtonRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOperatorMenuOpen]);

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
        {role === ROLE_ADMIN && (
          <div className="admin-role-badge">관리자</div>
        )}
        {isOperator(role) && (
          <div className="operator-menu" ref={operatorMenuRef}>
            <button
              type="button"
              className="operator-menu-button"
              ref={operatorButtonRef}
              aria-expanded={isOperatorMenuOpen}
              aria-controls="operator-menu-dropdown"
              onClick={() => setIsOperatorMenuOpen((isOpen) => !isOpen)}
            >
              운영자
            </button>
            {isOperatorMenuOpen && (
              <div className="operator-menu-dropdown" id="operator-menu-dropdown">
                <Link href="/admin/users" onClick={() => setIsOperatorMenuOpen(false)}>
                  회원 관리
                </Link>
                <Link href="/admin/visitors" onClick={() => setIsOperatorMenuOpen(false)}>
                  방문자 통계
                </Link>
              </div>
            )}
          </div>
        )}
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
