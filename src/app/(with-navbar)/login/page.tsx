"use client";

import { useSession } from "@/app/SessionContext";
import styles from "./page.module.css";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";

export default function Page() {
  const { user } = useSession();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const onChangeInputUsername = (e) => {
    setUsername(e.target.value);
  }
  const onChangeInputPassword = (e) => {
    setPassword(e.target.value);
  }

  const onClickLoginButton = async () => {
    await fetch("http://localhost:8080/login",{
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
      credentials: "include",
      mode: 'cors'
    })

    router.push("/");
  }

  useEffect(() => {
    if (user) {
      router.push("/"); // 이미 로그인된 경우 메인 페이지로 이동
    }
  }, [user, router]) //user 값이 변경될 때 → 즉, 로그인 상태가 변할 때 (로그인 or 로그아웃)
                     //router 값이 변경될 때 → 사실상 router 객체는 변하지 않지만, Next.js는 useRouter()를 useEffect에서 안전하게 사용할 수 있도록 의존성 배열에 추가하는 것을 권장하고 있음.


  return (
    <div className={styles.container}>
      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>로그인</h1>
          <h2 className={styles.description}>내전 게임을 즐기기 위해 다양한 서비스를 제공하는 <p></p>롤 내전 도우미에 오신것을 환영합니다.</h2>
        </div>
        <div className={styles.input_container}>
          <input type="text" placeholder="아이디" onChange={onChangeInputUsername}/>
          <input type="password" placeholder="비밀번호" onChange={onChangeInputPassword}/>
          {/* //TODO 입력란이 비어있으면 엔터색상 회색으로 */}
          <button className={styles.login_button} onClick={()=>onClickLoginButton()}>→</button>
          <div className={styles.link_container}>
            <Link href="/findId" className={styles.link_div}>아이디 / 비밀번호 찾기</Link>
            <Link href="/signup" className={styles.link_div}>계정 생성</Link>
          </div>
        </div>
      </main>
    </div>
  );
}