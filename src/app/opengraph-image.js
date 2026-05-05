import { ImageResponse } from "next/og";
import { siteConfig } from "./site-config";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #111827 0%, #1f2937 50%, #0f172a 100%)",
          color: "#f8fafc",
          padding: "56px",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            height: "100%",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: "28px",
            padding: "48px",
            background: "rgba(15, 23, 42, 0.35)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                alignSelf: "flex-start",
                padding: "10px 18px",
                borderRadius: "999px",
                fontSize: 28,
                background: "rgba(59, 130, 246, 0.18)",
                color: "#bfdbfe",
              }}
            >
              League of Legends 5:5 Team Balancer
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                maxWidth: "880px",
              }}
            >
              <div style={{ fontSize: 72, fontWeight: 700, lineHeight: 1.1 }}>
                {siteConfig.name}
              </div>
              <div
                style={{
                  fontSize: 34,
                  lineHeight: 1.35,
                  color: "#cbd5e1",
                }}
              >
                소환사 정보를 불러와 내전 인원을 정리하고, 밸런스 있는 팀 조합을
                빠르게 만들 수 있습니다.
              </div>
            </div>
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-end",
            }}
          >
            <div style={{ fontSize: 30, color: "#93c5fd" }}>
              lolcivilwarhelper.kro.kr
            </div>
            <div style={{ fontSize: 26, color: "#94a3b8" }}>
              Riot data powered matchmaking helper
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
