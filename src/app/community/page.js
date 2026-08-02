"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import API_BASE_URL from "../utils/api";
import { clearAuthState, getAuthToken, isStoredLoginActive } from "../utils/auth";

const categories = [
  { value: "RECRUIT", label: "내전모집" },
  { value: "NOTICE", label: "공지사항" },
];

const MAX_VISIBLE_TITLE_LENGTH = 37;

const formatCommunityTitle = (title) => {
  const titleChars = [...(title || "")];
  if (titleChars.length <= MAX_VISIBLE_TITLE_LENGTH) {
    return title;
  }

  return `${titleChars.slice(0, MAX_VISIBLE_TITLE_LENGTH).join("")}...`;
};

const formatDate = (dateTimeText) => {
  if (!dateTimeText) {
    return "-";
  }

  const date = new Date(dateTimeText);
  if (Number.isNaN(date.getTime())) {
    return dateTimeText;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
};

function CommunityListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [posts, setPosts] = useState([]);
  const [notices, setNotices] = useState([]);
  const [pageInfo, setPageInfo] = useState({ page: 0, totalPages: 0, totalElements: 0 });
  const [isAdmin, setIsAdmin] = useState(false);
  const [isCommunityVisible, setIsCommunityVisible] = useState(false);
  const [noticeDisplayCount, setNoticeDisplayCount] = useState(2);
  const [isChecking, setIsChecking] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isSettingSaving, setIsSettingSaving] = useState(false);
  const [error, setError] = useState("");
  const [noticeMessage, setNoticeMessage] = useState("");

  const activeCategory = searchParams.get("category") || "RECRUIT";
  const currentPage = Number(searchParams.get("page") || "1");
  const safeCurrentPage = Number.isNaN(currentPage) || currentPage < 1 ? 1 : currentPage;
  const activeCategoryLabel = useMemo(
    () => categories.find((category) => category.value === activeCategory)?.label || "내전모집",
    [activeCategory]
  );

  useEffect(() => {
    const storedIsLoggedIn = isStoredLoginActive();
    const storedIsAdmin = storedIsLoggedIn && localStorage.getItem("role") === "ROLE_ADMIN";

    setIsAdmin(storedIsAdmin);
    loadCommunitySetting(storedIsAdmin);
  }, []);

  useEffect(() => {
    if (!isChecking) {
      loadPosts(activeCategory, safeCurrentPage);
    }
  }, [activeCategory, safeCurrentPage, isChecking]);

  const getOptionalHeaders = () => {
    const token = getAuthToken();
    return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  };

  const getAuthHeaders = () => {
    const token = getAuthToken();
    if (!token) {
      return null;
    }

    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  };

  const handleAuthError = () => {
    clearAuthState();
    alert("로그인이 필요합니다. 다시 로그인해주세요.");
    router.push("/login");
  };

  const loadCommunitySetting = async (adminAccess) => {
    try {
      const response = await fetch(`${API_BASE_URL}/community/settings`);
      if (!response.ok) {
        throw new Error("커뮤니티 설정을 불러오지 못했습니다.");
      }

      const result = await response.json();
      const setting = result.data ?? {};
      setIsCommunityVisible(Boolean(setting.visibleToUsers));
      setNoticeDisplayCount(setting.noticeDisplayCount ?? 2);

      if (!adminAccess && !setting.visibleToUsers) {
        alert("커뮤니티는 현재 공개되지 않았습니다.");
        router.push("/");
        return;
      }

      setIsChecking(false);
    } catch (err) {
      setError(err.message || "커뮤니티 설정을 불러오지 못했습니다.");
      setIsChecking(false);
    }
  };

  const loadPosts = async (category, page) => {
    setIsLoading(true);
    setError("");

    try {
      const endpoint = isAdmin ? `${API_BASE_URL}/admin/community/posts` : `${API_BASE_URL}/community/posts`;
      const response = await fetch(
        `${endpoint}?category=${category}&page=${page - 1}&size=10`,
        getOptionalHeaders()
      );

      if (response.status === 401) {
        handleAuthError();
        return;
      }

      if (response.status === 403) {
        setError("커뮤니티가 아직 일반 사용자에게 공개되지 않았습니다.");
        return;
      }

      if (!response.ok) {
        throw new Error("게시글 목록을 불러오지 못했습니다.");
      }

      const result = await response.json();
      const data = result.data ?? {};
      setNotices(data.notices ?? []);
      setPosts(data.posts ?? []);
      setPageInfo({
        page: data.page ?? 0,
        totalPages: data.totalPages ?? 0,
        totalElements: data.totalElements ?? 0,
      });
    } catch (err) {
      setError(err.message || "게시글 목록을 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const goPage = (page) => {
    router.push(`/community?category=${activeCategory}&page=${page}`);
  };

  const changeCategory = (category) => {
    router.push(`/community?category=${category}&page=1`);
  };

  const updateCommunitySetting = async (nextSetting) => {
    const headers = getAuthHeaders();
    if (!headers) {
      handleAuthError();
      return;
    }

    setIsSettingSaving(true);
    setError("");
    setNoticeMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/admin/community/settings`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({
          visibleToUsers: nextSetting.visibleToUsers,
          noticeDisplayCount: nextSetting.noticeDisplayCount,
        }),
      });

      if (response.status === 401 || response.status === 403) {
        handleAuthError();
        return;
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "커뮤니티 설정 저장에 실패했습니다.");
      }

      const result = await response.json();
      const setting = result.data ?? {};
      setIsCommunityVisible(Boolean(setting.visibleToUsers));
      setNoticeDisplayCount(setting.noticeDisplayCount ?? 2);
      setNoticeMessage("커뮤니티 설정을 저장했습니다.");
      window.dispatchEvent(new CustomEvent("community-setting-change", {
        detail: { visibleToUsers: Boolean(setting.visibleToUsers) },
      }));
      await loadPosts(activeCategory, safeCurrentPage);
    } catch (err) {
      setError(err.message || "커뮤니티 설정 저장에 실패했습니다.");
    } finally {
      setIsSettingSaving(false);
    }
  };

  if (isChecking) {
    return (
      <section className="community-page">
        <p className="admin-muted">커뮤니티 접근 권한을 확인하는 중입니다.</p>
      </section>
    );
  }

  return (
    <section className="community-board-page">
      <div className="community-board-header">
        <div>
          <span>{isAdmin ? "Admin Board" : "Community Board"}</span>
          <h1>커뮤니티</h1>
          <p>공지사항과 내전모집 글을 게시판 형태로 확인할 수 있습니다.</p>
        </div>
        <Link className="community-write-link" href={`/community/write?category=${activeCategory}`}>
          글쓰기
        </Link>
      </div>

      {isAdmin && (
        <div className="community-board-setting">
          <div>
            <strong>커뮤니티 탭 공개</strong>
            <p>ON이면 일반 사용자 네비바에 커뮤니티 탭이 보이고, OFF면 완전히 숨겨집니다.</p>
          </div>
          <button
            type="button"
            className={isCommunityVisible ? "community-toggle-btn active" : "community-toggle-btn"}
            disabled={isSettingSaving}
            aria-label={isCommunityVisible ? "커뮤니티 탭 숨기기" : "커뮤니티 탭 보이기"}
            onClick={() => updateCommunitySetting({
              visibleToUsers: !isCommunityVisible,
              noticeDisplayCount,
            })}
          >
            <span>{isCommunityVisible ? "ON" : "OFF"}</span>
          </button>
          <label className="community-notice-count-control">
            <span>상단 공지 노출</span>
            <select
              value={noticeDisplayCount}
              disabled={isSettingSaving}
              onChange={(event) => updateCommunitySetting({
                visibleToUsers: isCommunityVisible,
                noticeDisplayCount: Number(event.target.value),
              })}
            >
              {[0, 1, 2, 3, 4, 5].map((count) => (
                <option key={count} value={count}>{count}개</option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div className="community-board-toolbar">
        <div className="community-board-tabs">
          {categories.map((category) => (
            <button
              key={category.value}
              type="button"
              className={activeCategory === category.value ? "active" : ""}
              onClick={() => changeCategory(category.value)}
            >
              {category.label}
            </button>
          ))}
        </div>
        <span>총 {pageInfo.totalElements.toLocaleString()}개</span>
      </div>

      {noticeMessage && <p className="community-notice">{noticeMessage}</p>}
      {error && <p className="admin-error">{error}</p>}

      <div className="community-board-table">
        <div className="community-board-row community-board-head">
          <span>번호</span>
          <span>제목</span>
          <span>글쓴이</span>
          <span>등록일</span>
          <span>조회</span>
        </div>

        {activeCategory !== "NOTICE" && notices.map((notice) => (
          <Link className="community-board-row notice" href={`/community/${notice.no}`} key={`notice-${notice.no}`}>
            <span>공지</span>
            <span>
              <strong title={notice.title}>[공지사항] {formatCommunityTitle(notice.title)}</strong>
            </span>
            <span>{notice.writerId}</span>
            <span>{formatDate(notice.createdAt)}</span>
            <span>{notice.viewCount.toLocaleString()}</span>
          </Link>
        ))}

        {isLoading ? (
          <div className="community-board-empty">게시글을 불러오는 중입니다.</div>
        ) : posts.length === 0 ? (
          <div className="community-board-empty">{activeCategoryLabel} 게시글이 없습니다.</div>
        ) : (
          posts.map((post) => (
            <Link className="community-board-row" href={`/community/${post.no}`} key={post.no}>
              <span>{post.no}</span>
              <span>
                <strong title={post.title}>[{post.category === "NOTICE" ? "공지사항" : "내전모집"}] {formatCommunityTitle(post.title)}</strong>
              </span>
              <span>{post.writerId}</span>
              <span>{formatDate(post.createdAt)}</span>
              <span>{post.viewCount.toLocaleString()}</span>
            </Link>
          ))
        )}
      </div>

      <div className="community-pagination">
        <button type="button" disabled={safeCurrentPage <= 1} onClick={() => goPage(safeCurrentPage - 1)}>
          이전
        </button>
        <span>{safeCurrentPage} / {Math.max(pageInfo.totalPages, 1)}</span>
        <button
          type="button"
          disabled={pageInfo.totalPages === 0 || safeCurrentPage >= pageInfo.totalPages}
          onClick={() => goPage(safeCurrentPage + 1)}
        >
          다음
        </button>
      </div>
    </section>
  );
}

export default function CommunityPage() {
  return (
    <Suspense fallback={<section className="community-page"><p className="admin-muted">커뮤니티를 불러오는 중입니다.</p></section>}>
      <CommunityListPage />
    </Suspense>
  );
}
