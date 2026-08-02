"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import API_BASE_URL from "../../utils/api";
import { clearAuthState, getAuthToken } from "../../utils/auth";

const roleLabels = {
  ROLE_ADMIN: "관리자",
  ROLE_USER: "일반 회원",
};

const formatKoreanDateTime = (dateTimeText) => {
  if (!dateTimeText) {
    return "기록 없음";
  }

  const date = new Date(`${dateTimeText}Z`);
  if (Number.isNaN(date.getTime())) {
    return dateTimeText;
  }

  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const value = (type) => parts.find((part) => part.type === type)?.value ?? "";

  return `${value("year")}-${value("month")}-${value("day")} ${value("hour")}:${value("minute")}:${value("second")}`;
};

export default function AdminUsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [updatingUserNo, setUpdatingUserNo] = useState(null);

  const adminCount = useMemo(
    () => users.filter((user) => user.role === "ROLE_ADMIN").length,
    [users]
  );

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      alert("관리자 로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    const loadUsers = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/admin/users`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.status === 401) {
          clearAuthState();
          alert("로그인 세션이 만료되었습니다.");
          router.push("/login");
          return;
        }

        if (response.status === 403) {
          clearAuthState();
          setError("관리자 권한이 필요합니다. 관리자 계정으로 다시 로그인해주세요.");
          alert("관리자 권한이 필요합니다.");
          router.push("/login");
          return;
        }

        if (!response.ok) {
          throw new Error("회원 목록을 불러오지 못했습니다.");
        }

        const result = await response.json();
        setUsers(result.data ?? []);
      } catch (err) {
        setError(err.message || "회원 목록을 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    loadUsers();
  }, [router]);

  const updateRole = async (userNo, role) => {
    const token = getAuthToken();
    if (!token) {
      clearAuthState();
      router.push("/login");
      return;
    }

    setUpdatingUserNo(userNo);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/admin/users/${userNo}/role`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ role }),
      });

      if (response.status === 401) {
        clearAuthState();
        alert("로그인 세션이 만료되었습니다.");
        router.push("/login");
        return;
      }

      if (response.status === 403) {
        clearAuthState();
        setError("관리자 권한이 필요합니다. 관리자 계정으로 다시 로그인해주세요.");
        alert("관리자 권한이 필요합니다.");
        router.push("/login");
        return;
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "권한 변경에 실패했습니다.");
      }

      const result = await response.json();
      setUsers((prevUsers) =>
        prevUsers.map((user) => (user.no === userNo ? result.data : user))
      );
    } catch (err) {
      setError(err.message || "권한 변경에 실패했습니다.");
    } finally {
      setUpdatingUserNo(null);
    }
  };

  if (isLoading) {
    return (
      <section className="admin-page">
        <h1>회원관리</h1>
        <p className="admin-muted">회원 목록을 불러오는 중입니다.</p>
      </section>
    );
  }

  return (
    <section className="admin-page">
      <div className="admin-header">
        <div>
          <h1>회원관리</h1>
          <p>가입한 회원의 가입일과 권한 수준을 확인하고 변경할 수 있습니다.</p>
        </div>
      </div>

      <div className="admin-summary-grid">
        <article className="admin-summary-card">
          <span>전체 회원</span>
          <strong>{users.length.toLocaleString()}</strong>
        </article>
        <article className="admin-summary-card">
          <span>관리자</span>
          <strong>{adminCount.toLocaleString()}</strong>
        </article>
        <article className="admin-summary-card">
          <span>일반 회원</span>
          <strong>{(users.length - adminCount).toLocaleString()}</strong>
        </article>
      </div>

      {error && <p className="admin-error">{error}</p>}

      <div className="admin-table-panel">
        <h2>회원 목록</h2>
        <table className="admin-table admin-users-table">
          <thead>
            <tr>
              <th>번호</th>
              <th>아이디</th>
              <th>가입일</th>
              <th>권한 수준</th>
              <th>권한 변경</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan={5}>가입한 회원이 없습니다.</td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.no}>
                  <td>{user.no}</td>
                  <td>{user.userId}</td>
                  <td>{formatKoreanDateTime(user.createdAt)}</td>
                  <td>
                    <span className={`role-badge ${user.role === "ROLE_ADMIN" ? "admin" : "user"}`}>
                      {roleLabels[user.role] || user.role}
                    </span>
                  </td>
                  <td>
                    <select
                      className="admin-role-select"
                      value={user.role}
                      disabled={updatingUserNo === user.no}
                      onChange={(event) => updateRole(user.no, event.target.value)}
                    >
                      <option value="ROLE_USER">일반 회원</option>
                      <option value="ROLE_ADMIN">관리자</option>
                    </select>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
