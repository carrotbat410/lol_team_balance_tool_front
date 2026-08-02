import "./globals.css";
import Link from "next/link";
import NavbarRight from "./components/NavbarRight";
import LogoLink from "./components/LogoLink";
import NavMenu from "./components/NavMenu";
import VisitTracker from "./components/VisitTracker";
import { siteConfig } from "./site-config";

export const metadata = {
  metadataBase: new URL(siteConfig.url),
  title: {
    default: "롤 내전 도우미 | 롤 내전 팀 밸런스 맞추기",
    template: "%s | 롤 내전 도우미",
  },
  description: siteConfig.description,
  keywords: siteConfig.keywords,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName: siteConfig.name,
    title: "롤 내전 도우미 | 롤 내전 팀 밸런스 맞추기",
    description: siteConfig.description,
    url: siteConfig.url,
    images: [
      {
        url: siteConfig.ogImage,
        width: 1200,
        height: 630,
        alt: "롤 내전 도우미 공유 이미지",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "롤 내전 도우미 | 롤 내전 팀 밸런스 맞추기",
    description: siteConfig.description,
    images: [siteConfig.ogImage],
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.png", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  verification: {
    other: {
      "naver-site-verification": "5a3d178bfeb9361348a7ae0f804577bfc4d0e8c7",
    },
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        <VisitTracker />
        <div className="logo-wrap container">
          <LogoLink />
        </div>
        <nav className="navbar container">
          <div className="navbar-inner">
            <NavMenu />
            <div className="nav-right">
              <NavbarRight />
            </div>
          </div>
        </nav>
        <main className="container">{children}</main>
        <Link href="https://open.kakao.com/o/suvzT5Wf" target="_blank" className="contact-btn">문의하기</Link>
      </body>
    </html>
  );
}
