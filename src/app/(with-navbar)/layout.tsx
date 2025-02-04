import { ReactNode } from "react"
import NavigationBar from "../components/NavigationBar/NavigationBar"
import styles from "./layout.module.css"

export default function Layout({
    children,
}: {
    children: ReactNode
}) {
    return (
        <div className={styles.container}>
            <NavigationBar/>
            <div className={styles.page_container}>
                {children}
            </div>
        </div>
    )
}