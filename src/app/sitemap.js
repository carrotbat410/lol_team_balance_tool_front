import { siteConfig } from "./site-config";

const routes = ["/team-balancer", "/team-balancer/guide"];

export default function sitemap() {
  const lastModified = new Date();

  return routes.map((route) => ({
    url: `${siteConfig.url}${route}`,
    lastModified,
    changeFrequency: route.startsWith("/team-balancer") ? "weekly" : "monthly",
    priority: route === "/team-balancer" ? 1 : 0.7,
  }));
}
