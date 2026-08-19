const VISITOR_ID_KEY = "lolCivilWarVisitorId";

const createVisitorId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const getOrCreateVisitorId = () => {
  const storedVisitorId = localStorage.getItem(VISITOR_ID_KEY);
  if (storedVisitorId) {
    return storedVisitorId;
  }

  const visitorId = createVisitorId();
  localStorage.setItem(VISITOR_ID_KEY, visitorId);
  return visitorId;
};
