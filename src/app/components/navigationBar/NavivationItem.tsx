import Link from "next/link";
import styles from "./NavivationItem.module.css"
import Image from "next/image";
import logoImage from "/public/images/logo.webp"
import AuthButton from "@/app/components/AuthButton/AuthButton";

interface NavigationItemProps {
    label: string;
    href: string;
  }
  

export default function NavigationItem({ label, href }: NavigationItemProps)  {
    
    if(label == "로고") {
        return (
            <div className={styles.container}>
                <Link href={href} className={styles.navItem}>
                    <Image 
                    src={logoImage}
                    width={70}
                    height={40}
                    alt="logo image"
                    />
                </Link>
            </div>
        )
    }

    if(label == "로그인") {
        return (
            <AuthButton/>
        )
    }

    return (
        <div className={styles.container}>
            <Link href={href} className={styles.navItem}>
                {label}
            </Link>
        </div>
    )
}