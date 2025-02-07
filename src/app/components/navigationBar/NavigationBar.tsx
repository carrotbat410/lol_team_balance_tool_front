import styles from "./NavigationBar.module.css";
import NavigationItem from "./NavivationItem";

const menuItems = [
  { label: "로고", href: "/" },
  { label: "커뮤니티", href: "/freeBoard" },
  { label: "팀짜기", href: "/teamBalance" },
  { label: "문의하기", href: "/tmp1" },
  { label: "로그인", href: "/login" },
];

export default function NavigationBar() {
  return (
    <div className={styles.container}>
      {menuItems.map((item, index) => {
        return <NavigationItem key={index} label={item.label} href={item.href} />
      } )}
    </div>
  );
}
