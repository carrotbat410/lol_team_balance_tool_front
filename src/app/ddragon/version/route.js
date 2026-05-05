import { NextResponse } from "next/server";

const FALLBACK_VERSION = "14.24.1";

export async function GET() {
  try {
    const response = await fetch("https://ddragon.leagueoflegends.com/api/versions.json", {
      next: { revalidate: 3600 }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const versions = await response.json();
    const latestVersion = Array.isArray(versions) ? versions[0] : null;

    if (typeof latestVersion === "string" && latestVersion !== "") {
      return NextResponse.json({ version: latestVersion });
    }
  } catch (error) {
    console.error("Data Dragon version proxy failed:", error);
  }

  return NextResponse.json({ version: FALLBACK_VERSION });
}
