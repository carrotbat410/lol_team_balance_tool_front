import styles from "./NavigationBar.module.css";
import NavigationItem from "./NavivationItem";

const menuItems = [
  { label: "로고", href: "/" },
  { label: "tmp1", href: "/freeBoard" },
  { label: "tmp2", href: "/teamBalance" },
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
