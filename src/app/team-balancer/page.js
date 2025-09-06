"use client";
import { useEffect, useState, useCallback } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';

const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, delay);
  };
};

export default function TeamPage() {
  const [summoners, setSummoners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [iconVersion, setIconVersion] = useState("14.24.1");
  const [showAddForm, setShowAddForm] = useState(false);
  const [summonerName, setSummonerName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);
  const [teamAssignMode, setTeamAssignMode] = useState("GOLDEN_BALANCE");
  const [team1List, setTeam1List] = useState([]);
  const [team2List, setTeam2List] = useState([]);
  const [noTeamList, setNoTeamList] = useState([]);
  const [draggedSummoner, setDraggedSummoner] = useState(null);
  const [formMessage, setFormMessage] = useState({ type: '', text: '' });
  const [refreshingSummoner, setRefreshingSummoner] = useState(null);
  const router = useRouter();

  const handleSessionExpired = () => {
    setSessionExpired(true);
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('username');
    window.dispatchEvent(new Event('storage'));
    setTimeout(() => {
      router.push('/login');
    }, 2000);
  };

  const handleApiError = (status) => {
    if (status === 401) {
      alert("세션이 만료되었습니다. 다시 로그인 후 시도해주세요.");
      handleSessionExpired();
      return true;
    }
    if (status === 403) {
      alert("권한이 없어 요청이 거부되었습니다. 문의사항은 오픈 채팅을 통해 문의 부탁드립니다.");
      return true;
    }
    return false;
  };

  const handleDragStart = (e, summoner) => {
    setDraggedSummoner(summoner);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, targetTeam) => {
    e.preventDefault();
    if (!draggedSummoner) return;

    const isNewSummoner = !team1List.find(s => s.no === draggedSummoner.no) &&
                          !team2List.find(s => s.no === draggedSummoner.no) &&
                          !noTeamList.find(s => s.no === draggedSummoner.no);

    if (isNewSummoner) {
      const totalInTeams = team1List.length + team2List.length + noTeamList.length;
      if (totalInTeams >= 10) {
        alert('10명을 초과하여 배치할 수는 없습니다.');
        setDraggedSummoner(null);
        return;
      }
    }

    // 드롭 대상 팀 인원 제한 체크 (팀1/팀2는 최대 5명)
    if (targetTeam === 'team1' && team1List.find(s => s.no === draggedSummoner.no) == null) {
      if (team1List.length >= 5) {
        alert('1팀에는 최대 5명까지 배치할 수 있습니다.');
        setDraggedSummoner(null);
        return;
      }
    }
    if (targetTeam === 'team2' && team2List.find(s => s.no === draggedSummoner.no) == null) {
      if (team2List.length >= 5) {
        alert('2팀에는 최대 5명까지 배치할 수 있습니다.');
        setDraggedSummoner(null);
        return;
      }
    }

    // 기존 위치에서 제거
    setTeam1List(prev => prev.filter(s => s.no !== draggedSummoner.no));
    setTeam2List(prev => prev.filter(s => s.no !== draggedSummoner.no));
    setNoTeamList(prev => prev.filter(s => s.no !== draggedSummoner.no));
    setSummoners(prev => prev.filter(s => s.no !== draggedSummoner.no));

    // 새 위치에 추가
    switch (targetTeam) {
      case 'team1':
        setTeam1List(prev => [...prev, draggedSummoner]);
        break;
      case 'team2':
        setTeam2List(prev => [...prev, draggedSummoner]);
        break;
      case 'unassigned':
        setNoTeamList(prev => [...prev, draggedSummoner]);
        break;
      case 'summoner-list':
        setSummoners(prev => [...prev, draggedSummoner]);
        break;
    }
    setDraggedSummoner(null);
  };

  const handleGenerateResult = () => {
    const totalInZones = team1List.length + team2List.length + noTeamList.length;
    if (totalInZones !== 10) {
      alert('총 10명이 1팀/2팀/팀 미지정에 배치되어야 합니다. 현재 배치된 인원: ' + totalInZones + '명');
      return;
    }
    if (team1List.length > 5) {
      alert('1팀에는 최대 5명까지 배치할 수 있습니다. 현재: ' + team1List.length + '명');
      return;
    }
    if (team2List.length > 5) {
      alert('2팀에는 최대 5명까지 배치할 수 있습니다. 현재: ' + team2List.length + '명');
      return;
    }

    // TODO: 팀 밸런싱 로직 구현 / 현재는 통과만
    console.log('결과 생성:', { teamAssignMode, team1List, team2List, noTeamList });
  };

  const handleReset = () => {
    // 모든 팀 구역을 비우고 소환사 목록을 원래 상태로 복원
    setTeam1List([]);
    setTeam2List([]);
    setNoTeamList([]);
    
    // 소환사 목록을 원래 데이터로 복원
    const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
    if (isLoggedIn) {
      // 로그인된 경우 API에서 다시 가져오기
      fetchSummoners();
    } else {
      // 로그인 안된 경우 임시 데이터로 복원
      const tempData = getTempData();
      setSummoners(tempData);
    }
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
    setFormMessage({ type: '', text: '' });

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
          tagLine: tagLine.trim() === '' ? 'KR1' : tagLine
        })
      });
      
      if (handleApiError(res.status)) return;
      
      if (res.ok) {
        setFormMessage({ type: 'success', text: '유저를 추가했습니다.' });
        const summonersRes = await fetch('http://localhost:8080/summoners?size=30', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (handleApiError(summonersRes.status)) return;
        
        if (summonersRes.ok) {
          const data = await summonersRes.json();
          setSummoners(data.data.content);
        }
        
        setSummonerName("");
        setTagLine("");
      } else {
        if (res.status === 404) {
          setFormMessage({ type: 'error', text: '존재하지 않는 유저입니다.' });
        } else {
          console.error("소환사 추가 실패:", res.status);
          setFormMessage({ type: 'error', text: '소환사 추가에 실패했습니다. 잠시 후 다시 시도해주세요.' });
        }
      }
    } catch (error) {
      console.error("소환사 추가 중 오류:", error);
      setFormMessage({ type: 'error', text: '소환사 추가 중 오류가 발생했습니다.' });
    }

    setTimeout(() => {
      setFormMessage({ type: '', text: '' });
    }, 3000);
  };

  const handleCancelAdd = () => {
    setSummonerName("");
    setTagLine("");
    setShowAddForm(false);
    setFormMessage({ type: '', text: '' });
  };

  const handleDelete = async (summonerNo) => {
    if (!confirm('정말로 이 소환사를 삭제하시겠습니까?')) {
      return;
    }

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      const res = await fetch(`http://localhost:8080/summoner?no=${summonerNo}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (handleApiError(res.status)) return;

      if (res.ok) {
        setSummoners(prev => prev.filter(s => s.no !== summonerNo));
        alert('소환사가 삭제되었습니다.');
      } else {
        console.error("소환사 삭제 실패:", res.status);
        alert('소환사 삭제에 실패했습니다.');
      }
    } catch (error) {
      console.error("소환사 삭제 중 오류:", error);
      alert('소환사 삭제 중 오류가 발생했습니다.');
    }
  };

  const handleRefresh = useCallback(async (summonerName, tagLine, summonerNo) => {
    setRefreshingSummoner(summonerNo);
    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      const res = await fetch('http://localhost:8080/summoner', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          summonerName: summonerName,
          tagLine: tagLine
        })
      });

      if (handleApiError(res.status)) return;

      if (res.ok) {
        const result = await res.json();
        const updatedSummoner = result.data;
        
        setSummoners(prev => prev.map(s => 
          s.summonerName === updatedSummoner.summonerName && s.tagLine === updatedSummoner.tagLine 
          ? { ...s, ...updatedSummoner } 
          : s
        ));

        alert('소환사 정보가 갱신되었습니다.');
      } else {
        console.error("소환사 갱신 실패:", res.status);
        alert('소환사 정보 갱신에 실패했습니다.');
      }
    } catch (error) {
      console.error("소환사 갱신 중 오류:", error);
      alert('소환사 정보 갱신 중 오류가 발생했습니다.');
    } finally {
      setRefreshingSummoner(null);
    }
  }, []);

  const debouncedHandleRefresh = useCallback(debounce(handleRefresh, 300), [handleRefresh]);

  const fetchSummoners = async () => {
    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      const res = await fetch('http://localhost:8080/summoners?size=30', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (handleApiError(res.status)) return;
      
      if (res.ok) {
        const data = await res.json();
        setSummoners(data.data.content);
      } else {
        // API 실패 시 임시 데이터 사용
        const tempData = getTempData();
        setSummoners(tempData);
      }
    } catch (error) {
      // 에러 시 임시 데이터 사용
      const tempData = getTempData();
      setSummoners(tempData);
    }
  };

  useEffect(() => {
    const initializeData = async () => {
      const version = await getLatestIconImgVersion();
      setIconVersion(version);
      
      const loadSummoners = async () => {
        const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
        
        if (isLoggedIn) {
          await fetchSummoners();
        } else {
          // 로그인 안된 경우 임시 데이터 사용
          const tempData = getTempData();
          setSummoners(tempData);
        }
        setLoading(false);
      };

      loadSummoners();
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

  const renderTeamZone = (team, teamName, teamKey) => (
    <div 
      className={`team-zone ${teamKey}`}
      onDragOver={handleDragOver}
      onDrop={(e) => handleDrop(e, teamKey)}
    >
      <h3 className="team-title">{teamName}</h3>
      <div className="team-members">
        {team.map((summoner) => (
          <div 
            key={summoner.no} 
            className="team-member"
            draggable
            onDragStart={(e) => handleDragStart(e, summoner)}
          >
            <div className="member-profile">
              <Image 
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

  if (loading) {
    return (
      <div className="team-page">
        <div className="team-layout">
          <div className="team-left">
            <h2>팀 배치 ({team1List.length + team2List.length + noTeamList.length}/10)</h2>
            <p>로딩 중...</p>
          </div>
          <div className="team-right">
            <h2>소환사 목록 ({summoners.length}/30)</h2>
            <p>로딩 중...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="team-page">
      {/* {sessionExpired && (
        <div className="session-expired-notice">
          세션이 만료되었습니다. 다시 로그인 후 이용해주세요.
        </div>
      )} */}
      <div className="team-layout">
        <div className="team-left">
          <div className="team-header">
            <h2>팀 배치 ({team1List.length + team2List.length + noTeamList.length}/10)</h2>
            <div className="team-mode-selector">
              <span>팀 섞기 모드</span>
              <select 
                value={teamAssignMode} 
                onChange={(e) => setTeamAssignMode(e.target.value)}
                className="team-mode-select"
              >
                {/* //TODO 나중에 라인고려도 만들기 */}
                {/* <option value="lineBalance">황금 밸런스(라인고려)</option> */}
                <option value="GOLDEN_BALANCE">황금 밸런스</option>
                <option value="RANDOM">무작위</option>
              </select>
            </div>
          </div>
          <div className="team-zones">
            {renderTeamZone(team1List, "1팀", "team1")}
            {renderTeamZone(team2List, "2팀", "team2")}
            {renderTeamZone(noTeamList, "팀 미지정", "unassigned")}
          </div>
          <div className="team-actions">
            <button className="generate-result-btn" onClick={handleGenerateResult}>
              결과 생성
            </button>
            <button className="reset-btn" onClick={handleReset}>
              초기화
            </button>
          </div>
        </div>
        <div className="team-right">
          <h2>소환사 목록 ({summoners.length}/30)</h2>
          <div 
            className="summoner-list"
            style={{ maxHeight: '450px', overflowY: 'auto' }}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, 'summoner-list')}
          > 
            {summoners.map((summoner) => (
              <div 
                key={summoner.no} 
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
            ))}
          </div>
          {!localStorage.getItem('isLoggedIn') ? (
            <div className="login-notice">
              로그인 후, 친구들의 소환사계정을 추가하고 팀을 짜보세요!
            </div>
          ) : (
            <div className="add-summoner-section">
              {!showAddForm ? (
                <button className="add-summoner-btn" onClick={handleAddSummoner}>소환사 추가</button>
              ) : (
                <form className="add-summoner-form" onSubmit={handleSubmitAdd}>
                  <p className="form-hint">
                    추가할 유저의 닉네임과 태그라인을 입력해주세요.<br />
                    (태그라인 생략시 태그라인은 KR1으로 검색됩니다.)
                  </p>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="summonerName" className="form-label">소환사명</label>
                      <input
                        id="summonerName"
                        type="text"
                        value={summonerName}
                        onChange={(e) => setSummonerName(e.target.value)}
                        required
                        className="summoner-input"
                        placeholder="예) Hide on bush"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tagLine" className="form-label">태그라인</label>
                      <input
                        id="tagLine"
                        type="text"
                        value={tagLine}
                        onChange={(e) => setTagLine(e.target.value)}
                        className="summoner-input"
                        placeholder="예) KR1"
                      />
                    </div>
                  </div>
                  
                  {formMessage.text && (
                    <div className={`form-message ${formMessage.type}`}>
                      {formMessage.text}
                    </div>
                  )}

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