import { siteConfig } from "./site-config";

export default function manifest() {
  return {
    name: siteConfig.name,
    short_name: siteConfig.shortName,
    description: siteConfig.description,
    start_url: "/team-balancer",
    display: "standalone",
    background_color: "#1c1c1f",
    theme_color: "#1c1c1f",
    lang: "ko-KR",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
      {
        src: "/logo.webp",
        sizes: "512x512",
        type: "image/webp",
      },
    ],
  };
}
