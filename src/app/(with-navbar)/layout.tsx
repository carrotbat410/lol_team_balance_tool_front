import { ReactNode } from "react"

export default function Layout({
    children,
}: {
    children: ReactNode
}) {
    return (
        <div>
            <div>임시 네비게이션 바</div>
            {children}
        </div>
    )
}