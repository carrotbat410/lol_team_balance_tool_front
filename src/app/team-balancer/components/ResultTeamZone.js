"use client";
import Image from 'next/image';
import { getTierColor, getTierText, customImageLoader } from '../utils/utils';

const ResultTeamZone = ({ team, teamName, teamKey, iconVersion }) => {
  return (
    <div
      className={`team-zone ${teamKey}`}
    >
      <h3 className="team-title">{teamName}</h3>
      <div className="team-members">
        {team.map((summoner) => (
          <div
            key={summoner.no}
            className="team-member"
          >
            <div className="member-profile">
              <Image
                loader={customImageLoader}
                src={`https://ddragon.leagueoflegends.com/cdn/${iconVersion}/img/profileicon/${summoner.profileIconId}.png`}
                alt="프로필 아이콘"
                width={32}
                height={32}
              />
              <span className="member-level">{summoner.summonerLevel}</span>
            </div>
            <div className="member-info">
              <div className="member-name">{summoner.summonerName}#{summoner.tagLine}</div>
              <div
                className="member-tier"
                style={{ color: getTierColor(summoner.tier) }}
              >
                {getTierText(summoner.tier, summoner.rank)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResultTeamZone;