import { ReactNode } from "react"
import NavigationBar from "../components/navigationBar/NavigationBar"

export default function Layout({
    children,
}: {
    children: ReactNode
}) {
    return (
        <div>
            <NavigationBar/>
            {children}
        </div>
    )
}