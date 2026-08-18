'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import API_BASE_URL from '../utils/api';
import { clearAuthState, getAuthToken, isStoredLoginActive } from '../utils/auth';
import { canDeleteAccount } from '../community/permissions';

export default function MyAccountPage() {
  const [username, setUsername] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [isPasswordFormOpen, setIsPasswordFormOpen] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleteFormOpen, setIsDeleteFormOpen] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [role, setRole] = useState(null);
  const router = useRouter();

  useEffect(() => {
    if (!isStoredLoginActive()) {
      alert('로그인이 필요한 페이지입니다.');
      router.push('/login');
      return;
    }

    const storedUsername = localStorage.getItem('username');
    setRole(localStorage.getItem('role') || '');
    if (storedUsername) {
      setUsername(storedUsername);
    }
  }, [router]);

  const clearTeamState = () => {
    localStorage.removeItem('team1List');
    localStorage.removeItem('team2List');
    localStorage.removeItem('noTeamList');
  };

  const resetPasswordForm = () => {
    setCurrentPassword('');
    setNewPassword('');
    setNewPasswordConfirm('');
    setPasswordError('');
  };

  const handlePasswordChange = async (event) => {
    event.preventDefault();

    if (isChangingPassword) {
      return;
    }

    setPasswordError('');

    if (!currentPassword || !newPassword || !newPasswordConfirm) {
      setPasswordError('모든 비밀번호 항목을 입력해주세요.');
      return;
    }

    const newPasswordLength = Array.from(newPassword).length;
    if (newPasswordLength < 6 || newPasswordLength > 72) {
      setPasswordError('새 비밀번호는 6자 이상 72자 이하로 입력해주세요.');
      return;
    }

    const utf8Encoder = new TextEncoder();
    if (utf8Encoder.encode(newPassword).length > 72 || utf8Encoder.encode(newPasswordConfirm).length > 72) {
      setPasswordError('새 비밀번호는 UTF-8 기준 72바이트 이하로 입력해주세요.');
      return;
    }

    if (Object.is(currentPassword, newPassword)) {
      setPasswordError('새 비밀번호는 현재 비밀번호와 달라야 합니다.');
      return;
    }

    if (newPassword !== newPasswordConfirm) {
      setPasswordError('새 비밀번호 확인이 일치하지 않습니다.');
      return;
    }

    setIsChangingPassword(true);

    try {
      const response = await fetch(`${API_BASE_URL}/account/password`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({ currentPassword, newPassword, newPasswordConfirm }),
      });

      if (response.status === 401 || response.status === 403) {
        clearAuthState();
        clearTeamState();
        window.dispatchEvent(new Event('auth-change'));
        router.push('/login');
        return;
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        setPasswordError(errorBody?.message || '비밀번호 변경 중 오류가 발생했습니다.');
        return;
      }

      resetPasswordForm();
      clearAuthState();
      clearTeamState();
      window.dispatchEvent(new Event('auth-change'));
      alert('비밀번호가 변경되었습니다. 다시 로그인해주세요.');
      router.push('/login');
    } catch (error) {
      setPasswordError('서버와 연결할 수 없습니다.');
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleDeleteAccount = async (event) => {
    event.preventDefault();
    setDeleteError('');

    if (!deletePassword.trim()) {
      setDeleteError('비밀번호를 입력해주세요.');
      return;
    }

    const confirmed = window.confirm('정말 회원 탈퇴를 진행할까요? 계정, 등록한 소환사 정보, 작성한 게시글과 댓글이 삭제됩니다.');
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
          <button
            type="button"
            className="change-password-btn"
            aria-expanded={isPasswordFormOpen}
            aria-controls="password-change-form"
            onClick={() => {
              if (isPasswordFormOpen) {
                resetPasswordForm();
              }
              setIsPasswordFormOpen(!isPasswordFormOpen);
            }}
            disabled={isChangingPassword}
          >
            {isPasswordFormOpen ? '변경 취소' : '비밀번호 변경'}
          </button>
        </div>
        {isPasswordFormOpen && (
          <form id="password-change-form" className="password-change-form" onSubmit={handlePasswordChange}>
            <label htmlFor="current-password">현재 비밀번호</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              disabled={isChangingPassword}
            />
            <label htmlFor="new-password">새 비밀번호</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              disabled={isChangingPassword}
            />
            <label htmlFor="new-password-confirm">새 비밀번호 확인</label>
            <input
              id="new-password-confirm"
              type="password"
              autoComplete="new-password"
              value={newPasswordConfirm}
              onChange={(event) => setNewPasswordConfirm(event.target.value)}
              disabled={isChangingPassword}
            />
            {passwordError && <div className="password-change-error">{passwordError}</div>}
            <div className="password-change-form-actions">
              <button
                type="button"
                className="cancel-password-change-btn"
                onClick={() => {
                  resetPasswordForm();
                  setIsPasswordFormOpen(false);
                }}
                disabled={isChangingPassword}
              >
                취소
              </button>
              <button className="confirm-password-change-btn" type="submit" disabled={isChangingPassword}>
                {isChangingPassword ? '변경 중...' : '변경하기'}
              </button>
            </div>
          </form>
        )}
      </div>
      {role !== null && <div className="account-actions">
        {!canDeleteAccount(role) ? (
          <p className="admin-muted">관리자 및 운영자 계정은 회원 탈퇴를 할 수 없습니다.</p>
        ) : !isDeleteFormOpen ? (
          <button className="delete-account-btn" onClick={() => setIsDeleteFormOpen(true)}>회원 탈퇴</button>
        ) : (
          <form className="delete-account-form" onSubmit={handleDeleteAccount}>
            <h2>회원 탈퇴</h2>
            <p>탈퇴하면 계정, 등록한 소환사 정보, 작성한 게시글과 댓글이 삭제됩니다.</p>
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
      </div>}
    </div>
  );
}
