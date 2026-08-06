"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const KAKAO_LEFT_AD_UNIT = "DAN-8pdWxUtfaMLE4MzT";
const KAKAO_RIGHT_AD_UNIT = "DAN-iuwjV35517IHkKnO";
const AD_ENABLED_PATHS = ["/team-balancer", "/team-balancer/guide", "/community"];

export default function KakaoSideAds() {
  const pathname = usePathname();
  const shouldShowAds = AD_ENABLED_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));

  if (!shouldShowAds) {
    return null;
  }

  return (
    <>
      <aside className="kakao-side-ad kakao-side-ad-left" aria-label="왼쪽 광고">
        <ins
          className="kakao_ad_area"
          style={{ display: "none" }}
          data-ad-unit={KAKAO_LEFT_AD_UNIT}
          data-ad-width="160"
          data-ad-height="600"
        />
      </aside>
      <aside className="kakao-side-ad kakao-side-ad-right" aria-label="오른쪽 광고">
        <ins
          className="kakao_ad_area"
          style={{ display: "none" }}
          data-ad-unit={KAKAO_RIGHT_AD_UNIT}
          data-ad-width="160"
          data-ad-height="600"
        />
      </aside>
      <Script src="https://t1.kakaocdn.net/kas/static/ba.min.js" strategy="afterInteractive" async />
    </>
  );
}
