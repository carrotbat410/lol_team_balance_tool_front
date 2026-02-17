"use client";
import Image from 'next/image';
import { getTierColor, getTierText, customImageLoader } from '../utils/utils';

const SummonerCard = ({ summoner, iconVersion, handleDragStart, debouncedHandleRefresh, handleDelete, refreshingSummoner, isLoggedIn, isTierEditable, handleTierChange }) => {
  const winRate = summoner.wins + summoner.losses > 0
    ? Math.round((summoner.wins / (summoner.wins + summoner.losses)) * 100)
    : 0;

  const rankedTiers = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"];
  const highTiers = ["MASTER", "GRANDMASTER", "CHALLENGER"];
  const ranks = ["IV", "III", "II", "I"];

  return (
    <div
      className="summoner-card"
      draggable
      onDragStart={(e) => handleDragStart(e, summoner)}
    >
      {refreshingSummoner === summoner.no && (
        <div className="refresh-overlay">
          <div className="refresh-overlay-text">갱신중...</div>
        </div>
      )}
      <div className="summoner-profile">
        <div className="profile-icon">
          <Image
            loader={customImageLoader}
            src={`https://ddragon.leagueoflegends.com/cdn/${iconVersion}/img/profileicon/${summoner.profileIconId}.png`}
            alt="프로필 아이콘"
            width={40}
            height={40}
          />
          <span className="level">{summoner.summonerLevel}</span>
        </div>
        <div className="summoner-info">
          <div className={`summoner-name ${summoner.summonerName.length > 11 ? 'long' : ''}`}>
            {summoner.summonerName}#{summoner.tagLine}
          </div>
          {isTierEditable ? (
            <select
              className="summoner-tier-select"
              value={`${summoner.tier}_${summoner.rank}`}
              onChange={(e) => {
                const [tier, rank] = e.target.value.split('_');
                handleTierChange(summoner.no, tier, parseInt(rank, 10));
              }}
              style={{ color: getTierColor(summoner.tier), backgroundColor: '#1a1a1a', border: 'none', fontSize: '0.8rem' }}
              onClick={(e) => e.stopPropagation()} // 이벤트 전파 중지
            >
              <option value="UNRANKED_0">UNRANKED</option>
              {rankedTiers.flatMap(tier =>
                ranks.map((rank, i) => (
                  <option key={`${tier}_${4 - i}`} value={`${tier}_${4 - i}`}>{`${tier} ${rank}`}</option>
                ))
              )}
              {highTiers.map(tier => <option key={tier} value={`${tier}_1`}>{tier}</option>)}
            </select>
          ) : (
            <div
              className="summoner-tier"
              style={{ color: getTierColor(summoner.tier) }}
            >
              {getTierText(summoner.tier, summoner.rank)}
            </div>
          )}
          <div className="summoner-stats">
            승률: {winRate}% ({summoner.wins}승 {summoner.losses}패)
          </div>
        </div>
      </div>
      {isLoggedIn && (
        <div className="summoner-actions">
          <button
            className="action-btn refresh-btn"
            title={summoner.updatable ? "갱신" : "갱신한지 24시간이 지나지 않은 소환사입니다."}
            onClick={() => summoner.updatable && debouncedHandleRefresh(summoner.summonerName, summoner.tagLine, summoner.no)}
            disabled={!summoner.updatable}
          >🔄</button>
          <button className="action-btn delete-btn" title="삭제" onClick={() => handleDelete(summoner.no)}>✕</button>
        </div>
      )}
    </div>
  );
};

export default SummonerCard;