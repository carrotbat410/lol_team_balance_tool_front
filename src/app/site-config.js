const fallbackSiteUrl = "https://lolcivilwarhelper.kro.kr";

export const siteConfig = {
  name: "롤 내전 도우미",
  shortName: "롤 내전 도우미",
  description:
    "라이엇 전적 데이터를 바탕으로 리그 오브 레전드 내전 팀을 빠르게 나누고, 밸런스 있는 5:5 조합을 만드는 서비스입니다.",
  url: process.env.NEXT_PUBLIC_SITE_URL || fallbackSiteUrl,
  ogImage: "/opengraph-image",
  keywords: [
    "롤 내전",
    "롤 팀 밸런스",
    "롤 내전 팀짜기",
    "리그오브레전드 내전",
    "LOL 팀 밸런스",
    "내전 도우미",
  ],
  navLinks: [
    { url: "/team-balancer", name: "팀 밸런서" },
    { url: "/community", name: "커뮤니티" },
  ],
};
