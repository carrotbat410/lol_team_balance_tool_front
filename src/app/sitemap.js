import { siteConfig } from "./site-config";

const routes = ["", "/team-balancer", "/community", "/login", "/signup"];

export default function sitemap() {
  const lastModified = new Date();

  return routes.map((route) => ({
    url: `${siteConfig.url}${route}`,
    lastModified,
    changeFrequency: route === "/team-balancer" ? "weekly" : "monthly",
    priority: route === "/team-balancer" ? 1 : 0.6,
  }));
}
