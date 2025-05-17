export const ebayAuth = {
  // Initiate login by redirecting to the backend endpoint
  initiateLogin() {
    window.location.href = "http://localhost:5000/auth/ebay-login";
  },

  // Check if user is logged in by asking the backend
  async isLoggedIn() {
    try {
      const response = await fetch("http://localhost:5000/auth/status", {
        credentials: "include", // Important: include cookies
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      return data.authenticated;
    } catch (error) {
      console.error("Error checking login status:", error);
      return false;
    }
  },

  // Get user ID from backend
  async getUserId() {
    try {
      const response = await fetch("http://localhost:5000/auth/status", {
        credentials: "include",
      });

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return data.authenticated ? data.userId : null;
    } catch (error) {
      console.error("Error getting user ID:", error);
      return null;
    }
  },

  // Logout by calling backend endpoint
  async logout() {
    try {
      await fetch("http://localhost:5000/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Error logging out:", error);
    }
  },
};
