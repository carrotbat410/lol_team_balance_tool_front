import Link from "next/link";
import Image from "next/image";

export const metadata = {
  title: "롤 내전 팀짜기 사용법",
  description:
    "롤 내전 도우미에서 소환사를 추가하고 소환사 정보를 확인하는 기본 사용법을 안내합니다.",
  alternates: {
    canonical: "/team-balancer/guide",
  },
};

const guideSteps = [
  {
    number: "01",
    title: "로그인 및 소환사 추가",
    descriptionLines: [
      "- 로그인 후, 소환사 목록 하단의 추가 버튼을 눌러 닉네임과 태그라인을 입력하여 추가합니다.",
      "- 태그라인을 비우면 KR1 기준으로 검색됩니다.",
    ],
    image: {
      src: "/guide/summoner-add.png",
      alt: "소환사명과 태그라인을 입력해 소환사를 추가하는 화면",
      width: 774,
      height: 550,
      priority: true,
    },
  },
  {
    number: "02",
    title: "소환사 정보 확인",
    descriptionLines: [
      "- 추가된 소환사는 아이콘, 티어, 승률, 전적 정보와 함께 목록에 표시됩니다.",
      "- 티어 조정이 필요하다면, 티어부분을 클릭하여 원하는 티어로 변경할 수 있습니다.",
      "- 갱신한지 24시간이 지나면, 갱신버튼이 활성화 됩니다.",
    ],
    image: {
      src: "/guide/summoner-info.png",
      alt: "추가된 소환사의 티어와 승률 정보를 확인하는 화면",
      width: 710,
      height: 396,
    },
  },
  {
    number: "03",
    title: "팀 배치 및 팀 섞기 모드 설정",
    descriptionLines: [
      "- 내전에 참여하는 소환사 10명을 1팀, 2팀, 팀 미지정 영역으로 드래그해서 배치합니다.",
      "- 팀 섞기 모드에서 황금 밸런스 또는 무작위를 선택할 수 있습니다.",
    ],
    image: {
      src: "/guide/team-setting.png",
      alt: "소환사를 팀별로 배치하고 팀 섞기 모드를 설정하는 화면",
      width: 2540,
      height: 1748,
    },
  },
  {
    number: "04",
    title: "팀 결과 확인 및 복사",
    descriptionLines: [
      "- '결과 생성'버튼을 누르면 1팀과 2팀의 평균 티어를 확인할 수 있습니다.",
      "- 팀 구성이 마음에 들지 않으면 다시하기로 재배치할 수 있습니다.",
      "- '결과 복사하기' 버튼을 누른후, 채팅창에 붙여넣어 결과를 공유해보세요.",
    ],
    image: {
      src: "/guide/team-result.png",
      alt: "생성된 팀 결과와 결과 복사하기 버튼을 확인하는 화면",
      width: 2488,
      height: 1676,
    },
  },
];

function GuideImage({ image }) {
  return (
    <div className="guide-image-card">
      <Image
        src={image.src}
        alt={image.alt}
        width={image.width}
        height={image.height}
        className="guide-step-image"
        priority={image.priority}
      />
    </div>
  );
}

export default function TeamBalancerGuidePage() {
  return (
    <div className="guide-page">
      <section className="guide-hero">
        <h1 >롤 내전 도우미 - 팀짜기 사용법</h1>
        <p className="guide-eyebrow">라이엇 서버로부터 정보를 가져와 팀을 구성할 수 있습니다.</p>
      </section>

      <section className="guide-steps" aria-label="팀짜기 사용법 단계">
        {guideSteps.map((step) => (
          <article className="guide-step" key={step.number}>
            <div className="guide-step-copy">
              <span>{step.number}</span>
              <h2>{step.title}</h2>
              {step.descriptionLines ? (
                <p className="guide-step-lines">
                  {step.descriptionLines.map((line) => (
                    <span key={line}>{line}</span>
                  ))}
                </p>
              ) : (
                <p>{step.description}</p>
              )}
            </div>
            <GuideImage image={step.image} />
          </article>
        ))}
      </section>
    </div>
  );
}
