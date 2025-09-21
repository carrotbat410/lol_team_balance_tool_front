export const customImageLoader = ({ src }) => {
  return src;
};

export const debounce = (func, delay) => {
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

export const getTierColor = (tier) => {
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

export const getTierText = (tier, rank) => {
  if (tier === 'UNRANKED') return 'UNRANKED';
  if (tier === 'GRANDMASTER' || tier === 'MASTER') return tier;
  
  const rankText = rank === 1 ? 'I' : rank === 2 ? 'II' : rank === 3 ? 'III' : rank === 4 ? 'IV' : '';
  return `${tier} ${rankText}`;
};