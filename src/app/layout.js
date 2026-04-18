import "./globals.css";
import Link from 'next/link';
import NavbarRight from './components/NavbarRight';
import LogoLink from './components/LogoLink';

export const metadata = {
  title: "롤 내전 도우미 - 라이엇 데이터 연동을 통해 편리한 내전 팀 짜기",
  description: "롤 내전 도우미는 밸런스있게 팀짜기 서비스를 제공하는 사이트 입니다.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        <div className="logo-wrap container">
          <LogoLink />
        </div>
        <nav className="navbar container">
          <div className="navbar-inner">
            <ul className="nav-menu">
              <li><Link href="/community">커뮤니티</Link></li>
              <li><Link href="/team-balancer">팀짜기</Link></li>
            </ul>
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
