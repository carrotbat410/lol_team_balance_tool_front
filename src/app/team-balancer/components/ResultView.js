"use client";
import ResultTeamZone from './ResultTeamZone';
import SummonerPanel from './SummonerPanel';
import { getTierColor, getTierText } from '../utils/utils';

const ResultView = ({
  balancedTeams,
  handleBackToPlacement,
  handleCopyResult,
  iconVersion,
  // SummonerPanel props
  summoners,
  handleDragOver,
  handleDrop,
  isLoggedIn,
  showAddForm,
  handleAddSummoner,
  handleSubmitAdd,
  summonerName,
  setSummonerName,
  tagLine,
  setTagLine,
  formMessage,
  handleCancelAdd,
  handleDragStart,
  debouncedHandleRefresh,
  handleDelete,
  refreshingSummoner
}) => {
  return (
    <div className="team-page">
      <div className="team-layout">
        <div className="team-left">
          <div className="team-header" style={{ textAlign: 'center', marginBottom: '20px' }}>
            <h2>팀 결과</h2>
            <p style={{ fontSize: '1.2em' }}>게임 평균 티어: {balancedTeams.gameAvgTierRank}</p>
          </div>
          <div className="team-zones">
            <ResultTeamZone
              team={balancedTeams.team1List}
              teamName={`1팀 - 평균 티어: ${balancedTeams.team1AvgTierRank}`}
              teamKey="team1"
              iconVersion={iconVersion}
            />
            <ResultTeamZone
              team={balancedTeams.team2List}
              teamName={`2팀 - 평균 티어: ${balancedTeams.team2AvgTierRank}`}
              teamKey="team2"
              iconVersion={iconVersion}
            />
            <ResultTeamZone team={[]} teamName={' '} teamKey="unassigned" />
          </div>
          <div className="team-actions">
            <button className="reset-btn" onClick={handleBackToPlacement}>
              다시하기
            </button>
            <button className="generate-result-btn" onClick={handleCopyResult}>
              결과 복사하기
            </button>
          </div>
        </div>
        <SummonerPanel
          summoners={summoners}
          handleDragOver={handleDragOver}
          handleDrop={handleDrop}
          isLoggedIn={isLoggedIn}
          showAddForm={showAddForm}
          handleAddSummoner={handleAddSummoner}
          handleSubmitAdd={handleSubmitAdd}
          summonerName={summonerName}
          setSummonerName={setSummonerName}
          tagLine={tagLine}
          setTagLine={setTagLine}
          formMessage={formMessage}
          handleCancelAdd={handleCancelAdd}
          iconVersion={iconVersion}
          handleDragStart={handleDragStart}
          debouncedHandleRefresh={debouncedHandleRefresh}
          handleDelete={handleDelete}
          refreshingSummoner={refreshingSummoner}
        />
      </div>
    </div>
  );
};

export default ResultView;