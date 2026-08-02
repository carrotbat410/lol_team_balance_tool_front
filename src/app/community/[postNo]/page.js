"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import API_BASE_URL from "../../utils/api";
import { clearAuthState, getAuthToken, isStoredLoginActive } from "../../utils/auth";

const MAX_VISIBLE_TITLE_LENGTH = 37;

const formatCommunityTitle = (title) => {
  const titleChars = [...(title || "")];
  if (titleChars.length <= MAX_VISIBLE_TITLE_LENGTH) {
    return title;
  }

  return `${titleChars.slice(0, MAX_VISIBLE_TITLE_LENGTH).join("")}...`;
};

const formatDateTime = (dateTimeText) => {
  if (!dateTimeText) {
    return "-";
  }

  const date = new Date(dateTimeText);
  if (Number.isNaN(date.getTime())) {
    return dateTimeText;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
};

export default function CommunityDetailPage() {
  const { postNo } = useParams();
  const router = useRouter();
  const [post, setPost] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [username, setUsername] = useState("");
  const [comments, setComments] = useState([]);
  const [commentContent, setCommentContent] = useState("");
  const [editingCommentNo, setEditingCommentNo] = useState(null);
  const [editingContent, setEditingContent] = useState("");
  const [isCommentSaving, setIsCommentSaving] = useState(false);
  const [commentError, setCommentError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const storedIsLoggedIn = isStoredLoginActive();
    setIsAdmin(storedIsLoggedIn && localStorage.getItem("role") === "ROLE_ADMIN");
    setUsername(localStorage.getItem("username") || "");
    loadPost(storedIsLoggedIn && localStorage.getItem("role") === "ROLE_ADMIN");
  }, [postNo]);

  const getOptionalHeaders = () => {
    const token = getAuthToken();
    return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  };

  const loadPost = async (adminAccess) => {
    setIsLoading(true);
    setError("");

    try {
      const endpoint = adminAccess
        ? `${API_BASE_URL}/admin/community/posts/${postNo}`
        : `${API_BASE_URL}/community/posts/${postNo}`;
      const response = await fetch(endpoint, getOptionalHeaders());

      if (response.status === 401) {
        clearAuthState();
        router.push("/login");
        return;
      }

      if (response.status === 403) {
        setError("게시글을 볼 권한이 없습니다.");
        return;
      }

      if (!response.ok) {
        throw new Error("게시글을 불러오지 못했습니다.");
      }

      const result = await response.json();
      setPost(result.data);
      await loadComments();
    } catch (err) {
      setError(err.message || "게시글을 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
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

  const loadComments = async () => {
    setCommentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/community/posts/${postNo}/comments`, getOptionalHeaders());

      if (response.status === 401) {
        clearAuthState();
        router.push("/login");
        return;
      }

      if (response.status === 403) {
        setCommentError("댓글을 볼 권한이 없습니다.");
        return;
      }

      if (!response.ok) {
        throw new Error("댓글을 불러오지 못했습니다.");
      }

      const result = await response.json();
      setComments(result.data ?? []);
    } catch (err) {
      setCommentError(err.message || "댓글을 불러오지 못했습니다.");
    }
  };

  const handleCommentAuthError = () => {
    clearAuthState();
    alert("로그인이 필요합니다. 다시 로그인해주세요.");
    router.push("/login");
  };

  const createComment = async (event) => {
    event.preventDefault();

    const headers = getAuthHeaders();
    if (!headers) {
      alert("댓글 작성은 로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    setIsCommentSaving(true);
    setCommentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/community/posts/${postNo}/comments`, {
        method: "POST",
        headers,
        body: JSON.stringify({ content: commentContent }),
      });

      if (response.status === 401) {
        handleCommentAuthError();
        return;
      }

      if (response.status === 403) {
        throw new Error("댓글을 작성할 권한이 없습니다.");
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "댓글 저장에 실패했습니다.");
      }

      const result = await response.json();
      setComments((prevComments) => [...prevComments, result.data]);
      setCommentContent("");
    } catch (err) {
      setCommentError(err.message || "댓글 저장에 실패했습니다.");
    } finally {
      setIsCommentSaving(false);
    }
  };

  const startEditComment = (comment) => {
    setEditingCommentNo(comment.no);
    setEditingContent(comment.content);
    setCommentError("");
  };

  const cancelEditComment = () => {
    setEditingCommentNo(null);
    setEditingContent("");
  };

  const updateComment = async (commentNo) => {
    const headers = getAuthHeaders();
    if (!headers) {
      handleCommentAuthError();
      return;
    }

    setIsCommentSaving(true);
    setCommentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/community/posts/${postNo}/comments/${commentNo}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ content: editingContent }),
      });

      if (response.status === 401) {
        handleCommentAuthError();
        return;
      }

      if (response.status === 403) {
        throw new Error("댓글을 수정할 권한이 없습니다.");
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "댓글 수정에 실패했습니다.");
      }

      const result = await response.json();
      setComments((prevComments) =>
        prevComments.map((comment) => (comment.no === commentNo ? result.data : comment))
      );
      cancelEditComment();
    } catch (err) {
      setCommentError(err.message || "댓글 수정에 실패했습니다.");
    } finally {
      setIsCommentSaving(false);
    }
  };

  const deleteComment = async (commentNo) => {
    if (!window.confirm("댓글을 삭제할까요?")) {
      return;
    }

    const headers = getAuthHeaders();
    if (!headers) {
      handleCommentAuthError();
      return;
    }

    setIsCommentSaving(true);
    setCommentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/community/posts/${postNo}/comments/${commentNo}`, {
        method: "DELETE",
        headers,
      });

      if (response.status === 401) {
        handleCommentAuthError();
        return;
      }

      if (response.status === 403) {
        throw new Error("댓글을 삭제할 권한이 없습니다.");
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.message || "댓글 삭제에 실패했습니다.");
      }

      setComments((prevComments) => prevComments.filter((comment) => comment.no !== commentNo));
    } catch (err) {
      setCommentError(err.message || "댓글 삭제에 실패했습니다.");
    } finally {
      setIsCommentSaving(false);
    }
  };

  const canManagePost = post && (isAdmin || (post.category === "RECRUIT" && post.writerId === username));
  const isLoggedIn = Boolean(username) && isStoredLoginActive();

  if (isLoading) {
    return (
      <section className="community-board-page">
        <p className="admin-muted">게시글을 불러오는 중입니다.</p>
      </section>
    );
  }

  if (error || !post) {
    return (
      <section className="community-board-page">
        <p className="admin-error">{error || "게시글을 찾을 수 없습니다."}</p>
        <Link className="community-secondary-link" href="/community">목록</Link>
      </section>
    );
  }

  return (
    <section className="community-detail-page">
      <div className="community-detail-actions">
        <Link className="community-secondary-link" href={`/community?category=${post.category}&page=1`}>목록</Link>
        {canManagePost && (
          <Link className="community-write-link" href={`/community/write?postNo=${post.no}`}>수정</Link>
        )}
      </div>

      <article className="community-detail-card">
        <span>{post.category === "NOTICE" ? "공지사항" : "내전모집"}</span>
        <h1 title={post.title}>{formatCommunityTitle(post.title)}</h1>
        <div className="community-detail-meta">
          <span>글쓴이 {post.writerId}</span>
          <span>등록일 {formatDateTime(post.createdAt)}</span>
          <span>조회 {post.viewCount.toLocaleString()}</span>
        </div>
        <div className="community-detail-content">
          <p>{post.content}</p>
        </div>
      </article>

      <section className="community-comments-card">
        <div className="community-comments-header">
          <h2>댓글 {comments.length.toLocaleString()}개</h2>
          <span>게시글에 대한 의견을 남길 수 있습니다.</span>
        </div>

        {commentError && <p className="admin-error">{commentError}</p>}

        <div className="community-comment-list">
          {comments.length === 0 ? (
            <p className="community-board-empty">아직 댓글이 없습니다.</p>
          ) : (
            comments.map((comment) => {
              const canManageComment = isAdmin || comment.writerId === username;

              return (
                <article className="community-comment-item" key={comment.no}>
                  <div className="community-comment-meta">
                    <strong>{comment.writerId}</strong>
                    <span>{formatDateTime(comment.createdAt)}</span>
                  </div>

                  {editingCommentNo === comment.no ? (
                    <div className="community-comment-edit">
                      <textarea
                        value={editingContent}
                        disabled={isCommentSaving}
                        onChange={(event) => setEditingContent(event.target.value)}
                      />
                      <div className="community-comment-actions">
                        <button type="button" disabled={isCommentSaving} onClick={() => updateComment(comment.no)}>
                          저장
                        </button>
                        <button type="button" disabled={isCommentSaving} onClick={cancelEditComment}>
                          취소
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p>{comment.content}</p>
                      {canManageComment && (
                        <div className="community-comment-actions">
                          <button type="button" disabled={isCommentSaving} onClick={() => startEditComment(comment)}>
                            수정
                          </button>
                          <button type="button" className="danger" disabled={isCommentSaving} onClick={() => deleteComment(comment.no)}>
                            삭제
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </article>
              );
            })
          )}
        </div>

        <form className="community-comment-form" onSubmit={createComment}>
          <label htmlFor="community-comment-content">댓글 작성</label>
          <textarea
            id="community-comment-content"
            value={commentContent}
            disabled={!isLoggedIn || isCommentSaving}
            placeholder={isLoggedIn ? "댓글을 입력해주세요." : "로그인 후 댓글을 작성할 수 있습니다."}
            onChange={(event) => setCommentContent(event.target.value)}
            required
          />
          <div className="community-form-actions">
            <button className="community-primary-btn" type="submit" disabled={!isLoggedIn || isCommentSaving}>
              {isCommentSaving ? "저장 중..." : "댓글 저장"}
            </button>
          </div>
        </form>
      </section>
    </section>
  );
}
