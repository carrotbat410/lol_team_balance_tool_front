"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import API_BASE_URL from "../../utils/api";
import { clearAuthState, getAuthToken } from "../../utils/auth";

const formatDateLabel = (dateText) => {
  const [, month, day] = dateText.split("-");
  return `${Number(month)}/${Number(day)}`;
};

const formatKoreanDateTime = (dateTimeText) => {
  if (!dateTimeText) {
    return "-";
  }

  const utcDate = new Date(`${dateTimeText}Z`);
  if (Number.isNaN(utcDate.getTime())) {
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
  }).formatToParts(utcDate);
  const value = (type) => parts.find((part) => part.type === type)?.value ?? "";

  return `${value("year")}-${value("month")}-${value("day")} ${value("hour")}:${value("minute")}:${value("second")}`;
};

export default function AdminVisitorsPage() {
  const router = useRouter();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      alert("관리자 로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    const loadSummary = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/admin/visits/summary?days=30`, {
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
          alert("관리자 권한이 필요합니다.");
          router.push("/");
          return;
        }

        if (!response.ok) {
          throw new Error("방문자 통계를 불러오지 못했습니다.");
        }

        const result = await response.json();
        setSummary(result.data);
      } catch (err) {
        setError(err.message || "방문자 통계를 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    };

    loadSummary();
  }, [router]);

  const maxVisitors = useMemo(() => {
    if (!summary?.dailyStats?.length) {
      return 1;
    }

    return Math.max(...summary.dailyStats.map((stat) => stat.totalVisitors), 1);
  }, [summary]);
  const loggedInVisitors = summary?.loggedInVisitors ?? [];

  if (isLoading) {
    return (
      <section className="admin-page">
        <h1>방문자 통계</h1>
        <p className="admin-muted">방문자 데이터를 불러오는 중입니다.</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="admin-page">
        <h1>방문자 통계</h1>
        <p className="admin-error">{error}</p>
      </section>
    );
  }

  return (
    <section className="admin-page">
      <div className="admin-header">
        <div>
          <h1>방문자 통계</h1>
          <p>{summary.startDate}부터 {summary.endDate}까지의 고유 방문자 기준입니다.</p>
        </div>
      </div>

      <div className="admin-summary-grid">
        <article className="admin-summary-card">
          <span>최근 30일 고유 방문자</span>
          <strong>{summary.totalUniqueVisitors.toLocaleString()}</strong>
        </article>
        <article className="admin-summary-card">
          <span>일별 방문자 합계</span>
          <strong>{summary.totalDailyVisitors.toLocaleString()}</strong>
        </article>
        <article className="admin-summary-card">
          <span>로그인 방문자</span>
          <strong>{summary.loggedInUniqueVisitors.toLocaleString()}</strong>
        </article>
        <article className="admin-summary-card">
          <span>게스트 방문자</span>
          <strong>{summary.guestUniqueVisitors.toLocaleString()}</strong>
        </article>
      </div>

      <div className="admin-chart-panel">
        <div className="admin-chart-title">
          <h2>일일 방문자 그래프</h2>
          <span>최근 {summary.days}일</span>
        </div>
        <div className="admin-chart">
          {summary.dailyStats.map((stat) => {
            const barHeight = Math.max((stat.totalVisitors / maxVisitors) * 100, stat.totalVisitors > 0 ? 8 : 2);

            return (
              <div className="admin-chart-item" key={stat.date}>
                <div className="admin-chart-value">{stat.totalVisitors}</div>
                <div className="admin-chart-track">
                  <div
                    className="admin-chart-bar"
                    style={{ height: `${barHeight}%` }}
                    title={`${stat.date}: ${stat.totalVisitors}명`}
                  />
                </div>
                <div className="admin-chart-label">{formatDateLabel(stat.date)}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="admin-table-panel">
        <h2>로그인 방문자</h2>
        <table className="admin-table">
          <thead>
            <tr>
              <th>아이디</th>
              <th>방문일 수</th>
              <th>총 접속 수</th>
              <th>첫 방문일</th>
              <th>마지막 방문일</th>
              <th>마지막 접속</th>
            </tr>
          </thead>
          <tbody>
            {loggedInVisitors.length === 0 ? (
              <tr>
                <td colSpan={6}>최근 기간에 로그인 방문자가 없습니다.</td>
              </tr>
            ) : (
              loggedInVisitors.map((visitor) => (
                <tr key={visitor.userId}>
                  <td>{visitor.userId}</td>
                  <td>{visitor.visitDays}</td>
                  <td>{visitor.hitCount}</td>
                  <td>{visitor.firstVisitDate}</td>
                  <td>{visitor.lastVisitDate}</td>
                  <td>{formatKoreanDateTime(visitor.lastVisitedAt)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-table-panel">
        <h2>일별 상세</h2>
        <table className="admin-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>전체</th>
              <th>로그인</th>
              <th>게스트</th>
            </tr>
          </thead>
          <tbody>
            {[...summary.dailyStats].reverse().map((stat) => (
              <tr key={stat.date}>
                <td>{stat.date}</td>
                <td>{stat.totalVisitors}</td>
                <td>{stat.loggedInVisitors}</td>
                <td>{stat.guestVisitors}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
