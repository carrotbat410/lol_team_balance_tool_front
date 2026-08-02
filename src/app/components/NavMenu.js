"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import API_BASE_URL from "../utils/api";
import { isStoredLoginActive } from "../utils/auth";

export default function NavMenu() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [isCommunityVisible, setIsCommunityVisible] = useState(false);

  useEffect(() => {
    const syncRole = () => {
      setIsAdmin(isStoredLoginActive() && localStorage.getItem("role") === "ROLE_ADMIN");
    };

    const loadCommunitySetting = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/community/settings`);
        if (!response.ok) {
          return;
        }

        const result = await response.json();
        setIsCommunityVisible(Boolean(result.data?.visibleToUsers));
      } catch {
        setIsCommunityVisible(false);
      }
    };

    const handleCommunitySettingChange = (event) => {
      if (typeof event.detail?.visibleToUsers === "boolean") {
        setIsCommunityVisible(event.detail.visibleToUsers);
        return;
      }

      loadCommunitySetting();
    };

    syncRole();
    loadCommunitySetting();
    window.addEventListener("storage", syncRole);
    window.addEventListener("auth-change", syncRole);
    window.addEventListener("community-setting-change", handleCommunitySettingChange);

    return () => {
      window.removeEventListener("storage", syncRole);
      window.removeEventListener("auth-change", syncRole);
      window.removeEventListener("community-setting-change", handleCommunitySettingChange);
    };
  }, []);

  return (
    <ul className="nav-menu">
      <li><Link href="/team-balancer">팀짜기</Link></li>
      <li><Link href="/team-balancer/guide">팀짜기 사용법</Link></li>
      {(isAdmin || isCommunityVisible) && (
        <li><Link href="/community">커뮤니티</Link></li>
      )}
      {isAdmin && (
        <li><Link href="/admin/users">회원관리</Link></li>
      )}
    </ul>
  );
}
