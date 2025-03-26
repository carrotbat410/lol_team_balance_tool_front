import Link from "next/link";
import styles from "./NavivationItem.module.css"

interface NavigationItemProps {
    label: string;
    href: string;
  }
  

export default function NavigationItem({ label, href }: NavigationItemProps)  {

    return (
        <div className={styles.container}>
            <Link href={href} className={styles.navItem}>
                {label}
            </Link>
        </div>
    )
}