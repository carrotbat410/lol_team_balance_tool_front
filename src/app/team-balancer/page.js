"use client";
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import API_BASE_URL from '../utils/api';
import { debounce, getTierColor, getTierText } from './utils/utils';
import TeamZone from './components/TeamZone';
import SummonerPanel from './components/SummonerPanel';
import ResultView from './components/ResultView';

export default function TeamPage() {
  const [summoners, setSummoners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [iconVersion, setIconVersion] = useState("14.24.1");
  const [showAddForm, setShowAddForm] = useState(false);
  const [summonerName, setSummonerName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);
  const [teamAssignMode, setTeamAssignMode] = useState("GOLDEN_BALANCE");
  const [team1List, setTeam1List] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedTeam1 = localStorage.getItem('team1List');
      return savedTeam1 ? JSON.parse(savedTeam1) : [];
    }
    return [];
  });
  const [team2List, setTeam2List] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedTeam2 = localStorage.getItem('team2List');
      return savedTeam2 ? JSON.parse(savedTeam2) : [];
    }
    return [];
  });
  const [noTeamList, setNoTeamList] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedNoTeam = localStorage.getItem('noTeamList');
      return savedNoTeam ? JSON.parse(savedNoTeam) : [];
    }
    return [];
  });
  const [draggedSummoner, setDraggedSummoner] = useState(null);
  const [formMessage, setFormMessage] = useState({ type: '', text: '' });
  const [refreshingSummoner, setRefreshingSummoner] = useState(null);
  const [showResultView, setShowResultView] = useState(false);
  const [balancedTeams, setBalancedTeams] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setIsLoggedIn(localStorage.getItem('isLoggedIn') === 'true');
  }, []);

  const getAuthHeaders = (includeContentType = true) => {
    const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
    const headers = {};
    if (includeContentType) {
      headers['Content-Type'] = 'application/json';
    }
    if (token && token !== 'undefined') {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  // Save team lists to localStorage whenever they change
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('team1List', JSON.stringify(team1List));
    }
  }, [team1List]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('team2List', JSON.stringify(team2List));
    }
  }, [team2List]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('noTeamList', JSON.stringify(noTeamList));
    }
  }, [noTeamList]);

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

  const handleGenerateResult = async () => {
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

    try {
      const res = await fetch(`${API_BASE_URL}/team/balance`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          teamAssignMode,
          team1List,
          team2List,
          noTeamList
        })
      });

      if (handleApiError(res.status)) return;

      if (res.ok) {
        const result = await res.json();
        setBalancedTeams(result.data);
        setShowResultView(true);
      } else {
        const errorData = await res.json().catch(() => ({ message: 'An unknown error occurred.' }));
        alert(`팀 생성 실패: ${errorData.message}`);
      }
    } catch (error) {
      console.error("팀 생성 중 오류:", error);
      alert('팀 생성 중 오류가 발생했습니다.');
    }
  };

  const handleReset = () => {
    // 모든 팀 구역을 비우고 소환사 목록을 원래 상태로 복원
    setTeam1List([]);
    setTeam2List([]);
    setNoTeamList([]);
    setShowResultView(false);
    setBalancedTeams(null);
    localStorage.removeItem('team1List');
    localStorage.removeItem('team2List');
    localStorage.removeItem('noTeamList');
    
    // 소환사 목록을 원래 데이터로 복원
    if (isLoggedIn) {
      // 로그인된 경우 API에서 다시 가져오기
      fetchSummoners();
    } else {
      // 로그인 안된 경우 임시 데이터로 복원
      const tempData = getTempData();
      setSummoners(tempData);
    }
  };

  const handleBackToPlacement = () => {
    setShowResultView(false);
    setBalancedTeams(null);
  };

  const handleCopyResult = () => {
    if (!balancedTeams) return;

    const team1Names = balancedTeams.team1List.map(s => s.summonerName).join(', ');
    const team2Names = balancedTeams.team2List.map(s => s.summonerName).join(', ');

    const copyText = `1팀: ${team1Names}\n2팀: ${team2Names}`;

    navigator.clipboard.writeText(copyText)
      .then(() => {
        alert('결과를 복사하였습니다. \n채팅창에 붙여넣어 친구들에게 공유해주세요!');
      })
      .catch(err => {
        console.error('클립보드 복사 실패:', err);
        alert('클립보드 복사에 실패했습니다.');
      });
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
      const res = await fetch(`${API_BASE_URL}/summoner`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          summonerName: summonerName,
          tagLine: tagLine.trim() === '' ? 'KR1' : tagLine
        })
      });
      
      if (handleApiError(res.status)) return;
      
      if (res.ok) {
        setFormMessage({ type: 'success', text: '유저를 추가했습니다.' });
        await fetchSummoners();
        
        setSummonerName("");
        setTagLine("");
      } else {
        const errorData = await res.json().catch(() => null);
        const errorMessage = errorData?.message || '소환사 추가에 실패했습니다. 잠시 후 다시 시도해주세요.';

        if (res.status === 404) {
          setFormMessage({ type: 'error', text: '존재하지 않는 유저입니다.' });
        } else if (res.status === 409 || res.status === 422) {
          setFormMessage({ type: 'error', text: errorMessage });
        } else {
          console.error("소환사 추가 실패:", res.status);
          setFormMessage({ type: 'error', text: errorMessage });
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
      const res = await fetch(`${API_BASE_URL}/summoner?no=${summonerNo}`, {
        method: 'DELETE',
        headers: getAuthHeaders(false)
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
      const res = await fetch(`${API_BASE_URL}/summoner`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
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
      const res = await fetch(`${API_BASE_URL}/summoners?size=30`, {
        headers: getAuthHeaders(false)
      });
      
      if (handleApiError(res.status)) return;
      
      if (res.ok) {
        const data = await res.json();
        const allFetchedSummoners = data.data.content;
        const placedSummonerNos = new Set([
          ...team1List.map(s => s.no),
          ...team2List.map(s => s.no),
          ...noTeamList.map(s => s.no)
        ]);
        const filteredSummoners = allFetchedSummoners.filter(s => !placedSummonerNos.has(s.no));
        setSummoners(filteredSummoners);
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
        const loggedIn = localStorage.getItem('isLoggedIn') === 'true';
        setIsLoggedIn(loggedIn);
        
        if (loggedIn) {
          await fetchSummoners();
          // 로그인 시 팀 목록 초기화
          setTeam1List([]);
          setTeam2List([]);
          setNoTeamList([]);
          localStorage.removeItem('team1List');
          localStorage.removeItem('team2List');
          localStorage.removeItem('noTeamList');
        } else {
          // 로그인 안된 경우 임시 데이터 사용 및 팀 목록 초기화
          const tempData = getTempData();
          setSummoners(tempData);
          setTeam1List([]);
          setTeam2List([]);
          setNoTeamList([]);
        }
        setLoading(false);
      };

      loadSummoners();
    };

    initializeData();

    const handleStorageChange = () => {
      initializeData();
    };

    window.addEventListener('storage', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const handleTierChange = (summonerNo, newTier, newRank) => {
    const newTierMMR = (() => {
        switch (newTier) {
            case "CHALLENGER":
            case "GRANDMASTER":
            case "MASTER":
                return 29;
            case "DIAMOND":
                return 25 + (4 - newRank);
            case "EMERALD":
                return 21 + (4 - newRank);
            case "PLATINUM":
                return 17 + (4 - newRank);
            case "GOLD":
                return 13 + (4 - newRank);
            case "SILVER":
                return 9 + (4 - newRank);
            case "BRONZE":
                return 5 + (4 - newRank);
            case "IRON":
                return 1 + (4 - newRank);
            default: // UNRANKED
                return 0;
        }
    })();

    const updateSummoner = (list) => list.map(s =>
        s.no === summonerNo ? { ...s, tier: newTier, rank: newRank, mmr: newTierMMR } : s
    );

    setSummoners(prev => updateSummoner(prev));
    setTeam1List(prev => updateSummoner(prev));
    setTeam2List(prev => updateSummoner(prev));
    setNoTeamList(prev => updateSummoner(prev));
  };

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

  if (showResultView && balancedTeams) {
    return (
      <ResultView
        balancedTeams={balancedTeams}
        handleBackToPlacement={handleBackToPlacement}
        handleCopyResult={handleCopyResult}
        iconVersion={iconVersion}
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
        handleDragStart={handleDragStart}
        debouncedHandleRefresh={debouncedHandleRefresh}
        handleDelete={handleDelete}
        refreshingSummoner={refreshingSummoner}
        handleTierChange={handleTierChange}
      />
    );
  }

  return (
    <div className="team-page">
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
                <option value="GOLDEN_BALANCE">황금 밸런스</option>
                <option value="RANDOM">무작위</option>
              </select>
            </div>
          </div>
          <div className="team-zones">
            <TeamZone
              team={team1List}
              teamName="1팀"
              teamKey="team1"
              handleDragOver={handleDragOver}
              handleDrop={handleDrop}
              handleDragStart={handleDragStart}
              iconVersion={iconVersion}
            />
            <TeamZone
              team={team2List}
              teamName="2팀"
              teamKey="team2"
              handleDragOver={handleDragOver}
              handleDrop={handleDrop}
              handleDragStart={handleDragStart}
              iconVersion={iconVersion}
            />
            <TeamZone
              team={noTeamList}
              teamName="팀 미지정"
              teamKey="unassigned"
              handleDragOver={handleDragOver}
              handleDrop={handleDrop}
              handleDragStart={handleDragStart}
              iconVersion={iconVersion}
            />
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
          isTierEditable={true}
          handleTierChange={handleTierChange}
        />
      </div>
    </div>
  );
}