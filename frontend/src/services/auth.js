export const appAuth = {
  // Initiate login by redirecting to eBay OAuth flow
  initiateEbayLogin(clientId) {
    // const bypassParam = "bypass-tunnel-reminder=true"; // Removing for same-origin focus
    // const redirectUrl = `/auth/ebay-login?client_id=${clientId}&${bypassParam}`;
    const redirectUrl = `/auth/ebay-login?client_id=${clientId}`; // Relative path
    window.location.href = redirectUrl;
  },

  // Check if token is valid
  async checkStatus(token) {
    try {
      const response = await fetch(
        "/auth/check-session", // Changed to relative path
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            // "bypass-tunnel-reminder": "true", // May be removed if not using a tunnel
            // "User-Agent": "TampermonkeyClient", // Consider if still needed
          },
          body: JSON.stringify({ session_id: token }),
        }
      );

      if (!response.ok) {
        // Try to parse error from backend if available
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

  // Poll for auth status with database-backed session
  async pollForAuthCompletion(clientId, maxAttempts = 90, interval = 2000) {
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const intervalId = setInterval(async () => {
        try {
          console.log(
            `Polling attempt ${
              attempts + 1
            }/${maxAttempts} for client ${clientId}`
          );

          const response = await fetch(
            `/auth/poll-status?client_id=${clientId}`, // Changed to relative path
            {
              method: "GET",
              headers: {
                Accept: "application/json",
                "Cache-Control": "no-cache",
                // "bypass-tunnel-reminder": "true", // May be removed
                // "User-Agent": "TampermonkeyClient", // Consider if still needed
              },
            }
          );

          attempts++;

          // Check content type to avoid parsing HTML as JSON
          const contentType = response.headers.get("content-type");
          if (!contentType || !contentType.includes("application/json")) {
            console.error(`Received non-JSON response: ${contentType}`);
            const text = await response.text();
            console.error(
              `Response body (first 100 chars): ${text.substring(0, 100)}`
            );

            if (attempts >= maxAttempts) {
              clearInterval(intervalId);
              reject(
                new Error(
                  "Max polling attempts reached, server returned non-JSON response."
                )
              );
              return;
            }
            return; // Continue polling
          }

          if (!response.ok) {
            const errorData = await response
              .json()
              .catch(() => ({ error: `Server error: ${response.status}` }));
            console.error("Polling error response:", errorData);
            if (attempts >= maxAttempts) {
              clearInterval(intervalId);
              reject(
                new Error(
                  errorData.error ||
                    `Server error: ${response.status} after max attempts.`
                )
              );
              return;
            }
            return; // Continue polling
          }

          const data = await response.json();
          console.log(`Poll response:`, data);

          if (data.authenticated) {
            clearInterval(intervalId);
            resolve({
              authenticated: true,
              sessionToken: data.session_token,
              userId: data.user_id,
              ebayUsername: data.ebay_username,
            });
          } else if (data.error) {
            // If backend indicates an error during polling (e.g. client_id not found, or explicit error)
            console.warn(`Polling returned error: ${data.error}`);
            if (attempts >= maxAttempts) {
              clearInterval(intervalId);
              reject(new Error(data.error || "Max polling attempts reached."));
            }
            // Continue polling unless it's a definitive error that should stop it.
            // For now, we continue until maxAttempts or success.
          } else if (attempts >= maxAttempts) {
            clearInterval(intervalId);
            reject(
              new Error("Max polling attempts reached without authentication.")
            );
          }
        } catch (error) {
          console.error("Error polling auth status:", error);
          attempts++;
          if (attempts >= maxAttempts) {
            clearInterval(intervalId);
            reject(error);
          }
        }
      }, interval);
      // Perform first check immediately
      // Note: The original code had an immediate check then setInterval.
      // This setInterval will run the first check after `interval` ms.
      // If an immediate check is desired, call the async function once before setInterval.
      // For simplicity here, relying on setInterval's first tick.
    });
  },

  // Logout
  async logout(sessionToken) {
    try {
      await fetch(
        "/auth/logout", // Changed to relative path
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            // "bypass-tunnel-reminder": "true", // May be removed
            // "User-Agent": "TampermonkeyClient", // Consider if still needed
          },
          body: JSON.stringify({ session_id: sessionToken }),
        }
      );
    } catch (error) {
      console.error("Error logging out:", error);
    }
  },

  // Add this method to check if we've just returned from eBay auth
  checkForAuthReturn() {
    const urlParams = new URLSearchParams(window.location.search);
    const authSuccess = urlParams.get("auth") === "success";
    const clientIdFromUrl = urlParams.get("client_id"); // Get client_id from URL
    const error = urlParams.get("error");

    if (authSuccess && clientIdFromUrl) {
      console.log(
        "auth.js: Detected return from eBay authentication with success for client_id:",
        clientIdFromUrl
      );
      let cleanUrl = window.location.pathname;
      history.replaceState({}, document.title, cleanUrl);
      return {
        isReturn: true,
        success: true,
        clientId: clientIdFromUrl,
        error: null,
      };
    } else if (error) {
      console.error(
        "auth.js: Detected return from eBay authentication with error:",
        error,
        "Details:",
        urlParams.get("details")
      );
      let cleanUrl = window.location.pathname;
      history.replaceState({}, document.title, cleanUrl);
      return {
        isReturn: true,
        success: false,
        clientId: clientIdFromUrl, // Still return clientId if present, even on error
        error: error,
      };
    }
    return { isReturn: false };
  },

  // Check if API is reachable
  async checkApiHealth() {
    try {
      const response = await fetch(
        "/health", // Changed to relative path
        {
          method: "GET",
          headers: {
            Accept: "application/json",
            "Cache-Control": "no-cache",
            // "bypass-tunnel-reminder": "true", // May be removed
            // "User-Agent": "TampermonkeyClient", // Consider if still needed
          },
        }
      );

      if (!response.ok) {
        return { status: "error", message: `API returned ${response.status}` };
      }
      const data = await response.json();
      return { status: "ok", data };
    } catch (error) {
      // Network error or non-JSON response
      console.error("API health check failed:", error);
      return { status: "error", message: error.message };
    }
  },
};
