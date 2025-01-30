import Link from "next/link";
import styles from "./NavivationItem.module.css"
import Image from "next/image";
import logoImage from "/public/images/logo.webp"

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
                    width={60}
                    height={30}
                    alt="logo image"
                    />
                </Link>
            </div>
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