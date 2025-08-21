"use client";
import { useEffect, useState } from 'react';
import Image from 'next/image';

export default function TeamPage() {
  const [summoners, setSummoners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [iconVersion, setIconVersion] = useState("14.24.1");
  const [showAddForm, setShowAddForm] = useState(false);
  const [summonerName, setSummonerName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);

  const handleSessionExpired = () => {
    setSessionExpired(true);
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('username');
    window.dispatchEvent(new Event('storage'));
  };

  const getLatestIconImgVersion = async () => {
    try {
      const response = await fetch("https://ddragon.leagueoflegends.com/api/versions.json");
      const versions = await response.json();
      const latestVersion = versions[0];
      if (latestVersion && latestVersion !== "") {
        return latestVersion;
      }
    } catch (err) {
      console.error("라이엇에서 version 가져오기 실패:", err);
    }
    return "14.24.1";
  };

  const handleAddSummoner = () => {
    setShowAddForm(true);
  };

  const handleSubmitAdd = async (e) => {
    e.preventDefault();
    
    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      const res = await fetch('http://localhost:8080/summoner', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          summonerName: summonerName,
          tagLine: tagLine
        })
      });
      
      if (res.status === 403) {
        handleSessionExpired();
        return;
      }
      
      if (res.ok) {
        // 성공 시 소환사 목록 새로고침
        const summonersRes = await fetch('http://localhost:8080/summoners?size=30', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (summonersRes.status === 403) {
          handleSessionExpired();
          return;
        }
        
        if (summonersRes.ok) {
          const data = await summonersRes.json();
          setSummoners(data.data.content);
        }
        
        setSummonerName("");
        setTagLine("");
        setShowAddForm(false);
      } else {
        console.error("소환사 추가 실패:", res.status);
        // TODO: 에러 메시지 표시
      }
    } catch (error) {
      console.error("소환사 추가 중 오류:", error);
      // TODO: 에러 메시지 표시
    }
  };

  const handleCancelAdd = () => {
    setSummonerName("");
    setTagLine("");
    setShowAddForm(false);
  };

  useEffect(() => {
    const initializeData = async () => {
      const version = await getLatestIconImgVersion();
      setIconVersion(version);
      
      const fetchSummoners = async () => {
        const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
        
        if (isLoggedIn) {
          try {
            const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
            const res = await fetch('http://localhost:8080/summoners?size=30', {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            });
            
            if (res.status === 403) {
              handleSessionExpired();
              return;
            }
            
            if (res.ok) {
              const data = await res.json();
              setSummoners(data.data.content);
            } else {
              // API 실패 시 임시 데이터 사용
              setSummoners(getTempData());
            }
          } catch (error) {
            // 에러 시 임시 데이터 사용
            setSummoners(getTempData());
          }
        } else {
          // 로그인 안된 경우 임시 데이터 사용
          setSummoners(getTempData());
        }
        setLoading(false);
      };

      fetchSummoners();
    };

    initializeData();
  }, []);

  const getTempData = () => {
    return [
        {
            "no": 40,
            "summonerName": "Hide on bush",
            "tagLine": "KR1",
            "tier": "GRANDMASTER",
            "rank": 1,
            "mmr": 30,
            "summonerLevel": 1,
            "wins": 303,
            "losses": 236,
            "profileIconId": 6
        },
        {
            "no": 51,
            "summonerName": "괴물쥐",
            "tagLine": "KR3",
            "tier": "DIAMOND",
            "rank": 1,
            "mmr": 28,
            "summonerLevel": 1213,
            "wins": 460,
            "losses": 448,
            "profileIconId": 3463
        },
        {
            "no": 52,
            "summonerName": "Akaps",
            "tagLine": "KR1",
            "tier": "MASTER",
            "rank": 1,
            "mmr": 29,
            "summonerLevel": 698,
            "wins": 573,
            "losses": 578,
            "profileIconId": 3791
        },
        {
            "no": 53,
            "summonerName": "코뚱잉",
            "tagLine": "KR1",
            "tier": "GRANDMASTER",
            "rank": 1,
            "mmr": 30,
            "summonerLevel": 1341,
            "wins": 1217,
            "losses": 1179,
            "profileIconId": 25
        },
        {
            "no": 55,
            "summonerName": "고구마유시",
            "tagLine": "KR1",
            "tier": "DIAMOND",
            "rank": 4,
            "mmr": 25,
            "summonerLevel": 788,
            "wins": 16,
            "losses": 17,
            "profileIconId": 6795
        },
        {
            "no": 56,
            "summonerName": "엔마왓슨",
            "tagLine": "0311",
            "tier": "MASTER",
            "rank": 1,
            "mmr": 29,
            "summonerLevel": 1317,
            "wins": 236,
            "losses": 210,
            "profileIconId": 1385
        },
        {
            "no": 38,
            "summonerName": "6두콩",
            "tagLine": "KR1",
            "tier": "GRANDMASTER",
            "rank": 1,
            "mmr": 30,
            "summonerLevel": 832,
            "wins": 742,
            "losses": 692,
            "profileIconId": 4691
        },
        {
            "no": 39,
            "summonerName": "화사첨족",
            "tagLine": "KR1",
            "tier": "MASTER",
            "rank": 1,
            "mmr": 29,
            "summonerLevel": 312,
            "wins": 234,
            "losses": 203,
            "profileIconId": 6362
        },
        {
            "no": 44,
            "summonerName": "통티모바베큐",
            "tagLine": "0410",
            "tier": "UNRANKED",
            "rank": 0,
            "mmr": 0,
            "summonerLevel": 21,
            "wins": 0,
            "losses": 0,
            "profileIconId": 29
        },
        {
            "no": 47,
            "summonerName": "구민상담소",
            "tagLine": "KR1",
            "tier": "SILVER",
            "rank": 1,
            "mmr": 12,
            "summonerLevel": 673,
            "wins": 7,
            "losses": 8,
            "profileIconId": 6049
        },
        {
            "no": 48,
            "summonerName": "우요링",
            "tagLine": "KR1",
            "tier": "GOLD",
            "rank": 3,
            "mmr": 14,
            "summonerLevel": 301,
            "wins": 101,
            "losses": 86,
            "profileIconId": 548
        },
        {
            "no": 49,
            "summonerName": "강철 우엉",
            "tagLine": "KR1",
            "tier": "UNRANKED",
            "rank": 0,
            "mmr": 0,
            "summonerLevel": 272,
            "wins": 0,
            "losses": 0,
            "profileIconId": 6434
        },
        {
            "no": 50,
            "summonerName": "헌병조나단",
            "tagLine": "KR1",
            "tier": "GOLD",
            "rank": 3,
            "mmr": 14,
            "summonerLevel": 190,
            "wins": 23,
            "losses": 22,
            "profileIconId": 4568
        },
    ];
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'GRANDMASTER': return '#ff6b6b';
      case 'MASTER': return '#ff8e53';
      case 'DIAMOND': return '#4ecdc4';
      case 'PLATINUM': return '#45b7d1';
      case 'GOLD': return '#f9ca24';
      case 'SILVER': return '#a4b0be';
      case 'BRONZE': return '#cd7f32';
      default: return '#95a5a6';
    }
  };

  const getTierText = (tier, rank) => {
    if (tier === 'UNRANKED') return 'UNRANKED';
    if (tier === 'GRANDMASTER' || tier === 'MASTER') return tier;
    
    const rankText = rank === 1 ? 'I' : rank === 2 ? 'II' : rank === 3 ? 'III' : rank === 4 ? 'IV' : '';
    return `${tier} ${rankText}`;
  };

  if (loading) {
    return (
      <div className="team-page container">
        <div className="team-layout">
          <div className="team-left">
            <h2>팀 배치</h2>
            <p>로딩 중...</p>
          </div>
          <div className="team-right">
            <h2>소환사 목록</h2>
            <p>로딩 중...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="team-page container">
      {sessionExpired && (
        <div className="session-expired-notice">
          세션이 만료되었습니다. 다시 로그인 후 이용해주세요.
        </div>
      )}
      <div className="team-layout">
        <div className="team-left">
          <h2>팀 배치</h2>
          <p>팀 배치 영역 (구현 예정)</p>
        </div>
        <div className="team-right">
          <h2>소환사 목록</h2>
          <div className="summoner-list">
            {summoners.map((summoner) => (
              <div key={summoner.no} className="summoner-card">
                <div className="summoner-profile">
                  <div className="profile-icon">
                    <Image 
                      src={`https://ddragon.leagueoflegends.com/cdn/${iconVersion}/img/profileicon/${summoner.profileIconId}.png`}
                      alt="프로필 아이콘"
                      width={44}
                      height={44}
                    />
                    <span className="level">{summoner.summonerLevel}</span>
                  </div>
                  <div className="summoner-info">
                    <div className="summoner-name">
                      {summoner.summonerName}#{summoner.tagLine}
                    </div>
                    <div 
                      className="summoner-tier"
                      style={{ color: getTierColor(summoner.tier) }}
                    >
                      {getTierText(summoner.tier, summoner.rank)}
                    </div>
                    <div className="summoner-stats">
                      승률: {summoner.wins + summoner.losses > 0 
                        ? Math.round((summoner.wins / (summoner.wins + summoner.losses)) * 100)
                        : 0}% ({summoner.wins}승 {summoner.losses}패)
                    </div>
                  </div>
                </div>
                {localStorage.getItem('isLoggedIn') === 'true' && (
                  <div className="summoner-actions">
                    <button className="action-btn refresh-btn" title="갱신">🔄</button>
                    <button className="action-btn delete-btn" title="삭제">✕</button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {!localStorage.getItem('isLoggedIn') ? (
            <div className="login-notice">
              로그인 후, 나만의 소환사를 추가하고 팀을짜보세요!
            </div>
          ) : (
            <div className="add-summoner-section">
              {!showAddForm ? (
                <button className="add-summoner-btn" onClick={handleAddSummoner}>소환사 추가</button>
              ) : (
                <form className="add-summoner-form" onSubmit={handleSubmitAdd}>
                  <div className="form-row">
                    <input
                      type="text"
                      placeholder="소환사명"
                      value={summonerName}
                      onChange={(e) => setSummonerName(e.target.value)}
                      required
                      className="summoner-input"
                    />
                    <input
                      type="text"
                      placeholder="태그라인"
                      value={tagLine}
                      onChange={(e) => setTagLine(e.target.value)}
                      required
                      className="summoner-input"
                    />
                  </div>
                  <div className="form-buttons">
                    <button type="submit" className="submit-btn">추가</button>
                    <button type="button" className="cancel-btn" onClick={handleCancelAdd}>취소</button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
