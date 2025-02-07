import Link from "next/link";
import styles from "./page.module.css";

export default function LoginButton() {

  return (
    <div className={styles.login_container}>
        <Link href="/login">로그인</Link>
    </div>
  );
}
