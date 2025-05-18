export const ebayAuth = {
  // Initiate login by redirecting to the backend endpoint
  initiateLogin() {
    const loginUrl = "http://localhost:5000/auth/ebay-login";
    // Attempt to navigate the top-level window.
    // This is important if your chat widget or script is running inside an iframe.
    if (window.top) {
      window.top.location.href = loginUrl;
    } else {
      // Fallback if window.top is not accessible (e.g., sandboxed iframe without allow-top-navigation)
      // or if not in a frame.
      window.location.href = loginUrl;
    }
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
