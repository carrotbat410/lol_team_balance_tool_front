"use client";

import { useSession } from "@/app/SessionContext";
import { useRouter } from "next/navigation";
import LoginButton from "./LoginButton";

export default function AuthButton() {
  const { user, setUser }= useSession();
  const router = useRouter();

  const handleLogout = async () => {
    // await fetch("http://localhost:8080/api/logout", {
    //   method: "POST",
    //   credentials: "include",
    // });
    // setUser(null); // 전역 상태 초기화
    // router.push("/"); // 로그아웃 후 메인 페이지로 이동
  };
  
  return user ? (
    <button onClick={handleLogout}>로그아웃</button>
  ) : (
    <LoginButton/>
    // <Link href="/login">로그인</Link>
  );
}