"use client";

import { useSession } from "@/app/SessionContext";
import styles from "./page.module.css";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";

export default function Page() {
  const { user } = useSession();
  const router = useRouter();

  const [id, setId] = useState("");
  const [password, setPassword] = useState("");

  const onChangeInputId = (e) => {
    setId(e.target.value);
  }
  const onChangeInputPassword = (e) => {
    setPassword(e.target.value);
  }

  const onClickLoginButton = async () => {
    console.log(`로그인버튼클릭함---- id:${id} password:${password}`)
    // await fetch("https://localhost:8080/api/auth/login",{
      // method: "POST",
      // headers: {
      //   "Content-Type": "application/json",
      // },
      // body: JSON.stringify({ id, password }),
      // credentials: "include",
    // })
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
        <div className={styles.title}>로그인</div>
        <div className={styles.input_container}>
          <input type="text" placeholder="아이디" onChange={onChangeInputId}/>
          <input type="text" placeholder="비밀번호" onChange={onChangeInputPassword}/>
          <button className={styles.login_button} onClick={()=>onClickLoginButton()}>→</button>
          <Link href="/signup" className={styles.signup_div}>계정 생성</Link>
        </div>
      </main>
    </div>
  );
}