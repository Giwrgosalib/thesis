export const appAuth = {
  // Initiate login by redirecting to eBay OAuth flow
  initiateEbayLogin(clientId) {
    const redirectUrl = `/auth/ebay-login?client_id=${clientId}`;
    window.location.href = redirectUrl;
  },

  // Check if token is valid
  async checkStatus(token) {
    try {
      const response = await fetch("/auth/check-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ session_id: token }),
      });

      if (!response.ok) {
        try {
          const errorData = await response.json();
          return {
            authenticated: false,
            error: errorData.error || "Server error",
          };
        } catch (e) {
          return {
            authenticated: false,
            error: `Server error: ${response.status}`,
          };
        }
      }

      return await response.json();
    } catch (error) {
      console.error("Error checking auth status:", error);
      return { authenticated: false, error: error.message };
    }
  },

  // Store authentication data in localStorage
  storeAuthData(authData) {
    localStorage.setItem("appSessionToken", authData.sessionToken);
    localStorage.setItem("userId", authData.userId);
    localStorage.setItem("ebayUsername", authData.ebayUsername);
    localStorage.setItem("authTimestamp", Date.now().toString());
    console.log("Auth data stored in localStorage");
  },

  // Get authentication data from localStorage
  getStoredAuthData() {
    const sessionToken = localStorage.getItem("appSessionToken");
    const userId = localStorage.getItem("userId");
    const ebayUsername = localStorage.getItem("ebayUsername");
    const authTimestamp = localStorage.getItem("authTimestamp");

    if (sessionToken && userId && ebayUsername) {
      return {
        sessionToken,
        userId,
        ebayUsername,
        authTimestamp: parseInt(authTimestamp) || 0,
      };
    }
    return null;
  },

  // Clear authentication data from localStorage
  clearStoredAuthData() {
    localStorage.removeItem("appSessionToken");
    localStorage.removeItem("userId");
    localStorage.removeItem("ebayUsername");
    localStorage.removeItem("authTimestamp");
    localStorage.removeItem("authClientId");
    console.log("Auth data cleared from localStorage");
  },

  // Check if we've just returned from eBay auth and store the result
  async checkForAuthReturn() {
    const urlParams = new URLSearchParams(window.location.search);
    const authSuccess = urlParams.get("auth") === "success";
    const clientIdFromUrl = urlParams.get("client_id");
    const error = urlParams.get("error");

    if (authSuccess && clientIdFromUrl) {
      console.log("Detected successful return from eBay authentication");

      // Check the backend for the session data
      try {
        const response = await fetch(
          `/auth/poll-status?client_id=${clientIdFromUrl}`
        );
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated && data.session_token) {
            // Store auth data in localStorage
            this.storeAuthData({
              sessionToken: data.session_token,
              userId: data.user_id,
              ebayUsername: data.ebay_username,
            });

            // Clean URL
            let cleanUrl = window.location.pathname;
            history.replaceState({}, document.title, cleanUrl);

            return {
              isReturn: true,
              success: true,
              authData: {
                sessionToken: data.session_token,
                userId: data.user_id,
                ebayUsername: data.ebay_username,
              },
              error: null,
            };
          }
        }
      } catch (error) {
        console.error("Error fetching auth data:", error);
      }
    } else if (error) {
      console.error("Authentication error:", error);
      let cleanUrl = window.location.pathname;
      history.replaceState({}, document.title, cleanUrl);
      return {
        isReturn: true,
        success: false,
        error: error,
      };
    }

    return { isReturn: false };
  },

  // Logout
  async logout(sessionToken) {
    try {
      await fetch("/auth/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ session_id: sessionToken }),
      });
    } catch (error) {
      console.error("Error logging out:", error);
    } finally {
      this.clearStoredAuthData();
    }
  },

  // Check if API is reachable
  async checkApiHealth() {
    try {
      const response = await fetch("/health", {
        method: "GET",
        headers: {
          Accept: "application/json",
          "Cache-Control": "no-cache",
        },
      });

      if (!response.ok) {
        return { status: "error", message: `API returned ${response.status}` };
      }
      const data = await response.json();
      return { status: "ok", data };
    } catch (error) {
      console.error("API health check failed:", error);
      return { status: "error", message: error.message };
    }
  },
};
