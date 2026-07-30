import { siteConfig } from "../site-config";

export const metadata = {
  title: "롤 내전 도우미 - 롤 내전 팀짜기",
  description:
    "롤 내전 도우미에서 소환사 티어와 전적을 기준으로 롤 내전 팀짜기를 빠르게 진행하고, 밸런스 있는 5:5 팀 결과를 공유해보세요.",
  keywords: siteConfig.keywords,
  alternates: {
    canonical: "/team-balancer",
  },
  openGraph: {
    title: "롤 내전 도우미 | 롤 내전 팀짜기",
    description:
      "롤 내전 참가자 10명을 정리하고 티어 기반으로 밸런스 있는 5:5 팀짜기 결과를 빠르게 만들어보세요.",
    url: `${siteConfig.url}/team-balancer`,
  },
  twitter: {
    title: "롤 내전 도우미 | 롤 내전 팀짜기",
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
    "롤 내전 도우미",
    "롤 내전 팀짜기",
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
