const fallbackSiteUrl = "https://lolcivilwarhelper.kro.kr";

export const siteConfig = {
  name: "롤 내전 도우미",
  shortName: "롤 내전 도우미",
  description:
    "롤 내전 도우미는 소환사 티어와 전적을 바탕으로 리그 오브 레전드 내전 팀짜기와 5:5 팀 밸런스를 빠르게 도와주는 서비스입니다.",
  url: process.env.NEXT_PUBLIC_SITE_URL || fallbackSiteUrl,
  ogImage: "/opengraph-image",
  keywords: [
    "롤 내전",
    "롤 팀 밸런스",
    "롤 내전 팀짜기",
    "롤 내전 도우미",
    "롤 팀짜기",
    "롤 팀 섞기",
    "롤 5대5 팀짜기",
    "리그오브레전드 내전",
    "LOL 팀 밸런스",
    "내전 도우미",
  ],
  navLinks: [
    { url: "/team-balancer", name: "팀짜기" },
    { url: "/team-balancer/guide", name: "팀짜기 사용법" },
  ],
};
