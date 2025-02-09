import type { Metadata } from "next";
import { Noto_Sans_KR } from 'next/font/google';
import "./globals.css";
import Footer from "./components/Footer/Footer";
import { SessionProvider } from "./SessionContext";

const notoSansKR = Noto_Sans_KR({
  weight: ['100', '300', '400', '500', '700', '900'], // 사용하고자 하는 폰트 굵기 설정
  subsets: ['latin', 'cyrillic'], // 언어 설정 (필요에 따라 추가)
  display: 'swap', // 폰트 로딩 최적화
});


//TODO 메타데이터 나중에 동적으로 값 채워지도록 수정하기
export const metadata: Metadata = {
  title: "롤 내전 도우미",
  description: "내전 게임을 즐기기 위해 다양한 서비스를 제공하는 롤 내전 도우미입니다.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  return (
    <html lang="ko">
      <body className={notoSansKR.className}>
        <div className="container">
          <SessionProvider>
            <main className="main">{children}</main>
            <footer className="footer">
              <Footer/>
            </footer>
          </SessionProvider>
        </div>
      </body>
    </html>
  );
}
