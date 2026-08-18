export const ROLE_OPERATOR = "ROLE_OPERATOR";
export const ROLE_ADMIN = "ROLE_ADMIN";
export const ROLE_USER = "ROLE_USER";

export const hasAdminAccess = (role) => role === ROLE_OPERATOR || role === ROLE_ADMIN;
export const isOperator = (role) => role === ROLE_OPERATOR;
export const canManageRoles = isOperator;
export const canManageCommunitySettings = isOperator;
export const canReadPrivateCommunity = hasAdminAccess;
export const canManageCommunity = (role, isCommunityVisible) =>
  isOperator(role) || (role === ROLE_ADMIN && isCommunityVisible);
export const canWriteCommunity = (role, isCommunityVisible) =>
  isOperator(role) || ([ROLE_ADMIN, ROLE_USER].includes(role) && isCommunityVisible);
export const canWriteNotice = isOperator;
export const canDeleteAccount = (role) => role === ROLE_USER;
