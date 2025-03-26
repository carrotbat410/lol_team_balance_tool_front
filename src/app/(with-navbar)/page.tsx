'use client'
import { useSession } from "../SessionContext";
import styles from "./page.module.css";

export default function Home() {

  const { user } = useSession();
  console.log("인덱스페이지에서 user:", user)

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div>인덱스 페이지</div>
      </main>
      <footer className={styles.footer}>
      </footer>
    </div>
  );
}
