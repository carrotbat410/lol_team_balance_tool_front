import styles from "./page.module.css";

export default function Home() {

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
