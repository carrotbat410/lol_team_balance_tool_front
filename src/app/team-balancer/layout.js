import { siteConfig } from "../site-config";

export const metadata = {
  title: "롤 내전 팀 밸런서",
  description:
    "소환사 티어와 전적을 바탕으로 리그 오브 레전드 내전 5:5 팀을 빠르게 나누고 공유할 수 있습니다.",
  keywords: siteConfig.keywords,
  alternates: {
    canonical: "/team-balancer",
  },
  openGraph: {
    title: "롤 내전 도우미 | 팀 밸런서",
    description:
      "소환사 정보를 불러와 내전 팀을 정리하고 밸런스 있는 5:5 결과를 빠르게 만들어보세요.",
    url: `${siteConfig.url}/team-balancer`,
  },
  twitter: {
    title: "롤 내전 도우미 | 팀 밸런서",
    description:
      "리그 오브 레전드 내전 인원을 정리하고 5:5 팀 밸런스를 빠르게 맞춰보세요.",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: siteConfig.name,
  applicationCategory: "GameApplication",
  operatingSystem: "Web",
  description: siteConfig.description,
  url: `${siteConfig.url}/team-balancer`,
  inLanguage: "ko-KR",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "KRW",
  },
  featureList: [
    "롤 내전 팀 밸런싱",
    "소환사 티어 기반 팀 추천",
    "팀 결과 복사 및 공유",
    "드래그 앤 드롭 팀 배치",
  ],
};

export default function TeamBalancerLayout({ children }) {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {children}
    </>
  );
}
