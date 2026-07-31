'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import API_BASE_URL from '../utils/api';
import { clearAuthState, getAuthToken, isStoredLoginActive } from '../utils/auth';

export default function MyAccountPage() {
  const [username, setUsername] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleteFormOpen, setIsDeleteFormOpen] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!isStoredLoginActive()) {
      alert('로그인이 필요한 페이지입니다.');
      router.push('/login');
      return;
    }

    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      setUsername(storedUsername);
    }
  }, [router]);

  const clearTeamState = () => {
    localStorage.removeItem('team1List');
    localStorage.removeItem('team2List');
    localStorage.removeItem('noTeamList');
  };

  const handleDeleteAccount = async (event) => {
    event.preventDefault();
    setDeleteError('');

    if (!deletePassword.trim()) {
      setDeleteError('비밀번호를 입력해주세요.');
      return;
    }

    const confirmed = window.confirm('정말 회원 탈퇴를 진행할까요? 계정과 등록한 소환사 정보가 삭제됩니다.');
    if (!confirmed) {
      return;
    }

    setIsDeleting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/account`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({ password: deletePassword }),
      });

      if (response.status === 200) {
        clearAuthState();
        clearTeamState();
        window.dispatchEvent(new Event('auth-change'));
        alert('회원 탈퇴가 완료되었습니다.');
        router.push('/');
        return;
      }

      if (response.status === 401 || response.status === 403) {
        clearAuthState();
        clearTeamState();
        window.dispatchEvent(new Event('auth-change'));
        alert('세션이 만료되었습니다. 다시 로그인해주세요.');
        router.push('/login');
        return;
      }

      const errorBody = await response.json().catch(() => null);
      setDeleteError(errorBody?.message || '회원 탈퇴 중 오류가 발생했습니다.');
    } catch (error) {
      setDeleteError('서버와 연결할 수 없습니다.');
    } finally {
      setIsDeleting(false);
    }
  };

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
        {!isDeleteFormOpen ? (
          <button className="delete-account-btn" onClick={() => setIsDeleteFormOpen(true)}>회원 탈퇴</button>
        ) : (
          <form className="delete-account-form" onSubmit={handleDeleteAccount}>
            <h2>회원 탈퇴</h2>
            <p>탈퇴하면 계정과 등록한 소환사 정보가 삭제됩니다. 방문자 통계는 익명 기록으로 유지됩니다.</p>
            <label htmlFor="delete-password">현재 비밀번호</label>
            <input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              value={deletePassword}
              onChange={(event) => setDeletePassword(event.target.value)}
              disabled={isDeleting}
            />
            {deleteError && <div className="login-error">{deleteError}</div>}
            <div className="delete-account-form-actions">
              <button
                type="button"
                className="cancel-delete-account-btn"
                onClick={() => {
                  setIsDeleteFormOpen(false);
                  setDeletePassword('');
                  setDeleteError('');
                }}
                disabled={isDeleting}
              >
                취소
              </button>
              <button className="confirm-delete-account-btn" type="submit" disabled={isDeleting}>
                {isDeleting ? '탈퇴 처리 중...' : '탈퇴하기'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
