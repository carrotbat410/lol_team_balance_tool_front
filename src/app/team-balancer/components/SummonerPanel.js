"use client";
import SummonerCard from './SummonerCard';
import AddSummonerForm from './AddSummonerForm';

const SummonerPanel = ({
  summoners,
  handleDragOver,
  handleDrop,
  isLoggedIn,
  showAddForm,
  handleAddSummoner,
  // Props for AddSummonerForm
  handleSubmitAdd,
  summonerName,
  setSummonerName,
  tagLine,
  setTagLine,
  formMessage,
  handleCancelAdd,
  // Props for SummonerCard
  iconVersion,
  handleDragStart,
  debouncedHandleRefresh,
  handleDelete,
  refreshingSummoner,
  isTierEditable,
  handleTierChange
}) => {
  return (
    <div className="team-right">
      <h2>소환사 목록 ({summoners.length}/30)</h2>
      <div
        className="summoner-list"
        style={{ maxHeight: '450px', overflowY: 'auto' }}
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, 'summoner-list')}
      >
        {summoners.map((summoner) => (
          <SummonerCard
            key={summoner.no}
            summoner={summoner}
            iconVersion={iconVersion}
            handleDragStart={handleDragStart}
            debouncedHandleRefresh={debouncedHandleRefresh}
            handleDelete={handleDelete}
            refreshingSummoner={refreshingSummoner}
            isLoggedIn={isLoggedIn}
            isTierEditable={isTierEditable}
            handleTierChange={handleTierChange}
          />
        ))}
      </div>
      {!isLoggedIn ? (
        <div className="login-notice">
          로그인 후, 친구들의 소환사계정을<br />추가하고 내전에 사용할 팀을 짜보세요!
        </div>
      ) : (
        <div className="add-summoner-section">
          {!showAddForm ? (
            <button className="add-summoner-btn" onClick={handleAddSummoner}>소환사 추가</button>
          ) : (
            <AddSummonerForm
              handleSubmit={handleSubmitAdd}
              summonerName={summonerName}
              setSummonerName={setSummonerName}
              tagLine={tagLine}
              setTagLine={setTagLine}
              formMessage={formMessage}
              handleCancel={handleCancelAdd}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default SummonerPanel;