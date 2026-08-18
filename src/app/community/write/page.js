"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import API_BASE_URL from "../../utils/api";
import {
  clearAuthState,
  getAuthToken,
  isStoredLoginActive,
} from "../../utils/auth";
import { COMMUNITY_CATEGORIES, WRITABLE_MEMBER_CATEGORIES } from "../community";
import { canWriteCommunity, canWriteNotice, hasAdminAccess } from "../permissions";

export const dynamic = "force-dynamic";

const emptyForm = {
  category: "RECRUIT",
  title: "",
  content: "",
};

const communityCategoryValues = COMMUNITY_CATEGORIES.map((category) => category.value);

function CommunityWriteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const postNo = searchParams.get("postNo");
  const categoryQuery = searchParams.get("category");
  const requestedCategory = communityCategoryValues.includes(categoryQuery) ? categoryQuery : "RECRUIT";
  const [form, setForm] = useState({ ...emptyForm, category: requestedCategory });
  const [role, setRole] = useState("");
  const [isCommunityVisible, setIsCommunityVisible] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const storedIsLoggedIn = isStoredLoginActive();
    const storedRole = storedIsLoggedIn ? localStorage.getItem("role") || "" : "";

    if (!storedIsLoggedIn) {
      alert("글쓰기는 로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    setRole(storedRole);
    const storedUsername = localStorage.getItem("username") || "";
    initializePage(storedRole, storedUsername);
  }, [postNo]);

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

  const initializePage = async (storedRole, storedUsername) => {
    try {
      const response = await fetch(`${API_BASE_URL}/community/settings`);
      if (!response.ok) {
        throw new Error("커뮤니티 설정을 불러오지 못했습니다.");
      }

      const result = await response.json();
      const visibleToUsers = Boolean(result.data?.visibleToUsers);
      setIsCommunityVisible(visibleToUsers);

      if (!canWriteCommunity(storedRole, visibleToUsers)) {
        setError("비공개 커뮤니티에서는 운영자만 글을 작성하거나 수정할 수 있습니다.");
        setIsLoading(false);
        return;
      }

      if (!canWriteNotice(storedRole) && requestedCategory === "NOTICE" && !postNo) {
        setForm((prev) => ({ ...prev, category: "RECRUIT" }));
      }

      if (postNo) {
        await loadPost(hasAdminAccess(storedRole), storedUsername, storedRole);
      } else {
        setIsLoading(false);
      }
    } catch (err) {
      setError(err.message || "글쓰기 화면을 준비하지 못했습니다.");
      setIsLoading(false);
    }
  };

  const loadPost = async (adminAccess, currentUsername, currentRole) => {
    const headers = getAuthHeaders();
    if (!headers) {
      handleAuthError();
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const endpoint = adminAccess
        ? `${API_BASE_URL}/admin/community/posts/${postNo}`
        : `${API_BASE_URL}/community/posts/${postNo}`;
      const response = await fetch(endpoint, { headers: { Authorization: headers.Authorization } });

      if (response.status === 401) {
        handleAuthError();
        return;
      }

      if (response.status === 403) {
        throw new Error("이 게시글을 수정할 권한이 없습니다.");
      }

      if (!response.ok) {
        throw new Error("게시글을 불러오지 못했습니다.");
      }

      const result = await response.json();
      const post = result.data;
      if (!adminAccess && (!WRITABLE_MEMBER_CATEGORIES.includes(post.category) || post.writerId !== currentUsername)) {
        throw new Error("본인이 작성한 내전모집 또는 클랜홍보 글만 수정할 수 있습니다.");
      }
      if (post.category === "NOTICE" && !canWriteNotice(currentRole)) {
        throw new Error("공지사항은 운영자만 수정할 수 있습니다.");
      }

      setForm({
        category: post.category,
        title: post.title,
        content: post.content,
      });
    } catch (err) {
      setError(err.message || "게시글을 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const submitPost = async (event) => {
    event.preventDefault();

    const headers = getAuthHeaders();
    if (!headers) {
      handleAuthError();
      return;
    }

    if (!canWriteCommunity(role, isCommunityVisible)) {
      setError("게시글을 저장할 권한이 없습니다.");
      return;
    }

    if (!communityCategoryValues.includes(form.category)) {
      setError("올바른 카테고리를 선택해주세요.");
      return;
    }

    if (form.category === "NOTICE" && !canWriteNotice(role)) {
      setError("공지사항은 운영자만 작성하거나 수정할 수 있습니다.");
      return;
    }

    if (!hasAdminAccess(role) && !WRITABLE_MEMBER_CATEGORIES.includes(form.category)) {
      setError("일반 사용자는 내전모집 또는 클랜홍보 글만 작성할 수 있습니다.");
      return;
    }

    setIsSaving(true);
    setError("");

    try {
      const endpointBase = hasAdminAccess(role) ? `${API_BASE_URL}/admin/community/posts` : `${API_BASE_URL}/community/posts`;
      const response = await fetch(postNo ? `${endpointBase}/${postNo}` : endpointBase, {
        method: postNo ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(form),
      });

      if (response.status === 401) {
        handleAuthError();
        return;
      }

      if (response.status === 403) {
        throw new Error("게시글을 저장할 권한이 없습니다.");
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "게시글 저장에 실패했습니다.");
      }

      const result = await response.json();
      router.push(`/community/${result.data.no}`);
    } catch (err) {
      setError(err.message || "게시글 저장에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <section className="community-write-page">
        <p className="admin-muted">게시글을 불러오는 중입니다.</p>
      </section>
    );
  }

  if (!canWriteCommunity(role, isCommunityVisible)) {
    return (
      <section className="community-write-page">
        <p className="admin-error">{error || "게시글을 작성하거나 수정할 권한이 없습니다."}</p>
        <Link className="community-secondary-link" href="/community">목록</Link>
      </section>
    );
  }

  return (
    <section className="community-write-page">
      <div className="community-detail-actions">
        <Link className="community-secondary-link" href="/community">목록</Link>
      </div>

      <form className="community-write-form" onSubmit={submitPost}>
        <span>{postNo ? "Edit Post" : "New Post"}</span>
        <h1>{postNo ? "게시글 수정" : "글쓰기"}</h1>

        <label htmlFor="community-category">카테고리</label>
        <select
          id="community-category"
          value={form.category}
          disabled={isSaving}
          onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
        >
          <option value="RECRUIT">내전모집</option>
          <option value="CLAN_PROMOTION">클랜홍보</option>
          {canWriteNotice(role) && <option value="NOTICE">공지사항</option>}
        </select>

        <label htmlFor="community-title">제목</label>
        <input
          id="community-title"
          maxLength={160}
          value={form.title}
          disabled={isSaving}
          onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
          required
        />

        <label htmlFor="community-content">내용</label>
        <textarea
          id="community-content"
          value={form.content}
          disabled={isSaving}
          onChange={(event) => setForm((prev) => ({ ...prev, content: event.target.value }))}
          required
        />

        {error && <p className="admin-error">{error}</p>}

        <div className="community-form-actions">
          <button className="community-primary-btn" type="submit" disabled={isSaving}>
            {isSaving ? "저장 중..." : "저장하기"}
          </button>
        </div>
      </form>
    </section>
  );
}

export default function CommunityWritePage() {
  return (
    <Suspense fallback={<section className="community-write-page"><p className="admin-muted">글쓰기 화면을 불러오는 중입니다.</p></section>}>
      <CommunityWriteForm />
    </Suspense>
  );
}
