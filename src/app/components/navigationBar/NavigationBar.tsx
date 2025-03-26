import Link from "next/link";
import Image from "next/image";
import logoImage from "/public/images/logo.webp"
import styles from "./NavigationBar.module.css";
import NavigationItem from "./NavivationItem";
import AuthButton from "../AuthButton/AuthButton";

const menuItems = [
  { label: "커뮤니티", href: "/freeBoard" },
  { label: "팀짜기", href: "/teamBalance" },
  { label: "문의하기", href: "/tmp1" },
  { label: "로그인", href: "/login" },
];

export default function NavigationBar() {
  return (
    <div className={styles.container}>
      <Link href={"/"} className={styles.logo}>
          <Image 
            src={logoImage}
            alt="logo image"
            layout="fill"
            objectFit="cover"
          />
      </Link>
      <div className={styles.center_div}>
        {menuItems.map((item, index) => {
          return <NavigationItem key={index} label={item.label} href={item.href} />
        } )}
      </div>
      <div className={styles.auth_div}>
        <AuthButton/>
      </div>
    </div>
  );
}
