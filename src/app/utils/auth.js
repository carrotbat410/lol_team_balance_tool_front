export const getAuthToken = () => {
  if (typeof document === "undefined") {
    return null;
  }

  const token = document.cookie
    .split("; ")
    .find((row) => row.startsWith("token="))
    ?.split("=")[1];

  if (!token || token === "undefined") {
    return null;
  }

  return token;
};

export const isStoredLoginActive = () => {
  if (typeof window === "undefined") {
    return false;
  }

  return localStorage.getItem("isLoggedIn") === "true" && Boolean(getAuthToken());
};

export const clearAuthState = () => {
  if (typeof window !== "undefined") {
    localStorage.removeItem("isLoggedIn");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
  }

  if (typeof document !== "undefined") {
    document.cookie =
      "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax";
  }
};
