<!-- eslint-disable prettier/prettier -->
<template>
  <!-- Only the button is visible when chat is closed -->
  <v-btn
    class="chat-fab hover:scale-105 transition-transform duration-200"
    @click="toggleChat"
  >
    <div class="ebay-logo">
      <span class="e">e</span>
      <span class="b">b</span>
      <span class="a">a</span>
      <span class="y">y</span>
    </div>
  </v-btn>

  <!-- Chat Widget -->
  <transition name="fade-slide">
    <!-- The existing chat card when logged in -->
    <v-card v-if="isChatOpen && loggedIn" class="chat-card">
      <!-- Header -->
      <v-card-title class="d-flex align-center header">
        <div class="ebay-logo">
          <span class="e">e</span>
          <span class="b">b</span>
          <span class="a">a</span>
          <span class="y">y</span>
          <span class="text-subtitle-1 ml-2">AI Recommender</span>
        </div>
      </v-card-title>

      <!-- Chat History -->
      <v-card-text class="chat-history">
        <!-- Welcome Message -->
        <div v-if="showWelcomeMessage" class="ai">
          <v-card class="message-bubble ai">
            <v-card-text>
              <div v-if="isFirstMessageLoading" class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div v-else class="message-content">
                <p>
                  Hello! How can I assist you with finding products on eBay
                  today?
                </p>
                <small class="timestamp">{{ welcomeMessageTimestamp }}</small>
              </div>
            </v-card-text>
          </v-card>
        </div>
        <!-- Messages -->
        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="message.sender"
        >
          <v-card :class="['message-bubble', message.sender]">
            <v-card-text>
              <div class="message-content">
                <p v-if="!message.isProductResults">{{ message.text }}</p>
                <div v-else class="product-results">
                  <p class="mb-2">
                    Here are some products that match your search:
                  </p>
                  <div
                    v-for="(product, idx) in message.products"
                    :key="idx"
                    class="product-card mb-3"
                  >
                    <div class="d-flex">
                      <img
                        v-if="product.image && product.image.imageUrl"
                        :src="product.image.imageUrl"
                        class="product-image mr-2"
                        alt="Product"
                      />
                      <div>
                        <div class="product-title">{{ product.title }}</div>
                        <div class="product-price">
                          ${{ product.price.value }}
                          {{ product.price.currency }}
                        </div>
                        <div class="product-condition">
                          {{ product.condition }}
                        </div>
                        <a
                          :href="product.publicUrl"
                          target="_blank"
                          class="product-link"
                          >View on eBay</a
                        >
                      </div>
                    </div>
                  </div>
                </div>
                <small class="timestamp">{{ message.timestamp }}</small>
              </div>
            </v-card-text>
          </v-card>
        </div>

        <!-- Typing Indicator -->
        <div v-if="isTyping" class="ai">
          <v-card class="message-bubble ai">
            <v-card-text>
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </v-card-text>
          </v-card>
        </div>
      </v-card-text>

      <!-- Input Area -->
      <v-card-actions class="chat-input">
        <v-text-field
          v-model="userInput"
          placeholder="Type your query..."
          outlined
          dense
          hide-details
          color="primary"
          single-line
          auto-grow
          rows="1"
          @keyup.enter="sendMessage"
          :disabled="isLoading"
        ></v-text-field>
        <v-btn color="primary" @click="sendMessage" :loading="isLoading">
          Send
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- New login required card when NOT logged in -->
    <v-card v-else-if="isChatOpen && !loggedIn" class="chat-card login-card">
      <!-- Header without AI Recommender text -->
      <v-card-title class="d-flex align-center header">
        <div class="ebay-logo">
          <span class="e">e</span>
          <span class="b">b</span>
          <span class="a">a</span>
          <span class="y">y</span>
        </div>
        <v-spacer></v-spacer>
        <v-btn icon @click="toggleChat" class="close-btn">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <!-- Login Required Content -->
      <div class="login-required-content">
        <v-icon size="64" color="warning" class="mb-4">mdi-account-lock</v-icon>
        <h3 class="text-h5 mb-3">eBay Login Required</h3>
        <p class="text-body-1 mb-4">
          Please sign in to your eBay account to use the shopping assistant.
        </p>
        <v-btn @click="initiateEbaySignIn" class="login-btn">
          Sign in to eBay
        </v-btn>
        <p class="text-body-2 mt-4">
          After signing in, please refresh the page or click the chat button again.
        </p>
      </div>
    </v-card>
  </transition>
</template>
<script>
import { appAuth } from "../services/auth.js";

export default {
  name: "ChatBox",
  data() {
    return {
      userInput: "",
      messages: [],
      isChatOpen: false,
      isTyping: false,
      isLoading: false,
      showWelcomeMessage: false,
      isFirstMessageLoading: true,
      welcomeMessageTimestamp: "",
      apiBaseUrl: " https://secure-openly-moth.ngrok-free.app", // Changed to relative path

      // --- Authentication State (managed in component memory) ---
      loggedIn: false,
      userId: null,
      appSessionToken: null, // This will NOT be populated from URL parameters here.
      // It must be set by other means if a session is to be recognized.
      ebayUsername: null,
      // --- End Authentication State ---

      authError: "",
      authLoading: false,
      authCheckLoading: true,

      pollingActive: false,
      clientId: null, // Initialize clientId to null
      pollingInterval: null, // This might not be directly used if setInterval is managed in auth.js
    };
  },
  async mounted() {
    this.authCheckLoading = true;
    console.log("ChatBox mounted. Initial clientId:", this.clientId);

    const authReturn = appAuth.checkForAuthReturn(); // Checks URL params

    if (authReturn.isReturn) {
      if (authReturn.success && authReturn.clientId) {
        console.log(
          "Detected return from eBay auth, using clientId from URL:",
          authReturn.clientId
        );
        this.clientId = authReturn.clientId;
        sessionStorage.setItem("authClientId", this.clientId); // Store it for potential refreshes during polling
        this.startAuthPolling();
      } else if (authReturn.error) {
        this.authError = `Authentication failed: ${authReturn.error}. Please try again.`;
        this.authLoading = false;
        this.authCheckLoading = false;
        sessionStorage.removeItem("authClientId"); // Clear on error
      }
    } else {
      // Not an auth return, check for existing session token or ongoing polling via sessionStorage
      const storedClientId = sessionStorage.getItem("authClientId");
      if (storedClientId) {
        console.log("Found clientId in sessionStorage:", storedClientId);
        this.clientId = storedClientId;
      } else {
        // Generate a new one if no auth process is in flight and none in session storage
        this.clientId = "client_" + Math.random().toString(36).substring(2, 15);
        sessionStorage.setItem("authClientId", this.clientId); // Store new one
        console.log(
          "Generated new clientId and stored in sessionStorage:",
          this.clientId
        );
      }

      // Now check if we have an appSessionToken or need to resume polling
      await this.performAuthCheck(); // Checks existing appSessionToken
      if (!this.loggedIn && this.clientId && !this.pollingActive) {
        // If not logged in, but we have a clientId (possibly from sessionStorage indicating a prior attempt)
        // and not currently polling, consider resuming.
        // However, startAuthPolling is typically called after initiateEbaySignIn or authReturn.
        // This logic might need refinement based on desired resume behavior.
        // For now, checkAuthOnLoad handles resuming if clientId is set and no token.
        console.log(
          "No auth return, checking if polling needs to be resumed for clientId:",
          this.clientId
        );
        this.checkAuthOnLoad();
      }
    }
    // If the chat is intended to be open by default and user is logged in
    if (this.isChatOpen && this.loggedIn && !this.showWelcomeMessage) {
      this.showWelcomeMessage = true;
      this.simulateFirstMessageLoading();
    }
    this.authCheckLoading = false;
  },
  beforeUnmount() {
    this.pollingActive = false;
  },
  methods: {
    async performAuthCheck() {
      this.authCheckLoading = true;
      if (this.appSessionToken) {
        // Check if a token exists in component memory
        console.log("Performing auth check with token:", this.appSessionToken);
        const status = await appAuth.checkStatus(this.appSessionToken); // auth.js sends this token
        if (status.authenticated) {
          this.loggedIn = true;
          this.userId = status.userId;
          this.ebayUsername = status.ebayUsername;
          this.authError = "";
          console.log(
            "User session is active. User ID:",
            this.userId,
            "eBay Username:",
            this.ebayUsername
          );
        } else {
          // Token was invalid or session expired on backend
          this.loggedIn = false;
          this.appSessionToken = null; // Clear the invalid token from memory
          this.userId = null;
          this.ebayUsername = null;
          this.authError =
            status.error ||
            "Your session is invalid or has expired. Please sign in again.";
          console.warn(
            "Stored session token is invalid or session expired on backend."
          );
        }
      } else {
        // No session token in component memory, so user is not logged in
        this.loggedIn = false;
        this.userId = null;
        this.ebayUsername = null;
        console.log("No appSessionToken in memory. User is not logged in.");
      }
      this.authCheckLoading = false;
    },

    async toggleChat() {
      this.isChatOpen = !this.isChatOpen;
      if (this.isChatOpen) {
        console.log("Chat toggled open. Performing auth check.");
        // When chat opens, always check/verify authentication status
        // This will use this.appSessionToken if it's already in memory from a previous successful login
        // where the token was somehow passed to this component instance.
        await this.performAuthCheck();
        // If logged in and welcome message hasn't been shown, show it.
        if (this.loggedIn && !this.showWelcomeMessage) {
          this.showWelcomeMessage = true;
          this.simulateFirstMessageLoading();
        }
      }
    },

    async initiateEbaySignIn() {
      this.authLoading = true;
      this.authError = "";

      const healthCheck = await appAuth.checkApiHealth();
      if (healthCheck.status !== "ok") {
        this.authError = `API connection error: ${healthCheck.message}. Please ensure the backend is running.`;
        this.authLoading = false;
        return;
      }

      // Generate a new client ID for this specific auth attempt
      this.clientId = "client_" + Math.random().toString(36).substring(2, 15);
      sessionStorage.setItem("authClientId", this.clientId); // Store it
      console.log("Initiating eBay sign-in with new clientId:", this.clientId);

      this.startAuthPolling();
      appAuth.initiateEbayLogin(this.clientId);
    },

    startAuthPolling() {
      if (this.pollingActive) {
        console.warn("Polling is already active for clientId:", this.clientId);
        return;
      }
      if (!this.clientId) {
        console.error("Cannot start polling without a client ID.");
        this.authLoading = false;
        return;
      }

      this.pollingActive = true;
      this.authLoading = true;
      console.log(
        "Starting authentication polling with client ID:",
        this.clientId
      );

      appAuth
        .pollForAuthCompletion(this.clientId)
        .then((result) => {
          console.log("Authentication polling successful:", result);
          this.pollingActive = false;
          this.authLoading = false;
          sessionStorage.removeItem("authClientId"); // Clean up clientId on success

          this.loggedIn = true;
          this.appSessionToken = result.sessionToken;
          this.userId = result.userId;
          this.ebayUsername = result.ebayUsername;
          this.authError = "";

          if (!this.showWelcomeMessage) {
            this.showWelcomeMessage = true;
            this.simulateFirstMessageLoading();
          }
        })
        .catch((error) => {
          console.error("Authentication polling failed:", error);
          this.pollingActive = false;
          this.authLoading = false;
          this.authError =
            error.message || "Authentication polling timed out or failed.";
          sessionStorage.removeItem("authClientId"); // Clean up clientId on failure
        });
    },

    async checkAuthOnLoad() {
      // This method is called if no direct authReturn, to see if polling should resume
      const storedToken = sessionStorage.getItem("appSessionToken");
      if (storedToken) {
        // If there's a token, performAuthCheck should validate it.
        // This method is more about resuming polling if no token but a clientId exists.
        return;
      }

      // If we have a clientId (likely from sessionStorage from a previous attempt)
      // and no session token, and not already polling, try to resume.
      if (this.clientId && !this.appSessionToken && !this.pollingActive) {
        console.log(
          "checkAuthOnLoad: Resuming polling for clientId from sessionStorage:",
          this.clientId
        );
        this.startAuthPolling();
      } else {
        console.log(
          "checkAuthOnLoad: Conditions not met to resume polling. ClientId:",
          this.clientId,
          "Token:",
          this.appSessionToken,
          "PollingActive:",
          this.pollingActive
        );
      }
    },

    async handleLogout() {
      if (this.appSessionToken) {
        await appAuth.logout(this.appSessionToken); // auth.js sends this token
      }
      // Clear client-side authentication state
      this.loggedIn = false;
      this.userId = null;
      this.appSessionToken = null; // Clear token from component memory
      this.ebayUsername = null;
      this.messages = [];
      this.showWelcomeMessage = false;
      this.authError = "";
      this.authCheckLoading = false;
      sessionStorage.removeItem("authClientId"); // Clear clientId on logout
      console.log(
        "User logged out. Client-side state, token, and authClientId cleared."
      );
    },

    async sendMessage() {
      // Ensure this.userId is not directly added to requestBody unless that's intended.
      // The backend should derive the user from the appSessionToken sent in the Authorization header.
      // The existing code from #attachment-ChatBox-vue-L238 sends requestBody.userId,
      // which might be redundant if the backend uses the session token for user identification.
      // For consistency with session token auth, it's better if backend relies on the token.
      // I will adjust it to match the pattern of sending the token in the header for auth.

      if (this.userInput.trim() === "") return;

      this.messages.push({
        sender: "user",
        text: this.userInput,
        timestamp: this.getCurrentTimestamp(),
      });

      const query = this.userInput;
      this.userInput = "";
      this.isTyping = true;
      this.isLoading = true;

      try {
        const requestBody = { query: query }; // Only send the query
        const headers = {
          "Content-Type": "application/json",
          "bypass-tunnel-reminder": "true",
          "User-Agent": "TampermonkeyClient",
        };

        if (this.loggedIn && this.appSessionToken) {
          headers["Authorization"] = `Bearer ${this.appSessionToken}`;
        } else {
          console.warn(
            "Sending search query without an active session token (user might not be logged in)."
          );
        }

        const response = await fetch(`/search`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({
            error: `Server responded with status: ${response.status}`,
          }));
          throw new Error(
            errorData.error ||
              `Server responded with status: ${response.status}`
          );
        }
        const data = await response.json();
        // ... (handle search results display as in your existing code, e.g., #attachment-ChatBox-vue-L262)
        if (data && data.length > 0) {
          this.messages.push({
            sender: "ai",
            isProductResults: true,
            products: data.slice(0, 5),
            text: `I found some products matching your search.`,
            timestamp: this.getCurrentTimestamp(),
          });
        } else {
          this.messages.push({
            sender: "ai",
            text: "I couldn't find any products matching your search. Could you try a different query?",
            timestamp: this.getCurrentTimestamp(),
          });
        }
      } catch (error) {
        console.error("Error fetching search results:", error);
        this.messages.push({
          sender: "ai",
          text: `Sorry, I encountered an error: ${
            error.message || "Please try again."
          }`,
          timestamp: this.getCurrentTimestamp(),
        });
      } finally {
        this.isTyping = false;
        this.isLoading = false;
      }
    },

    getCurrentTimestamp() {
      const now = new Date();
      return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    },

    simulateFirstMessageLoading() {
      this.isFirstMessageLoading = true;
      this.welcomeMessageTimestamp = "";
      setTimeout(() => {
        this.isFirstMessageLoading = false;
        this.welcomeMessageTimestamp = this.getCurrentTimestamp();
      }, 1000);
    },
  },
};
</script>

<style scoped>
/* Chat widget styling */
.chat-fab {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 100;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.chat-card {
  position: fixed;
  bottom: 90px;
  right: 20px;
  width: 350px;
  height: 500px;
  z-index: 99;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.header {
  background-color: #f8f8f8;
  border-bottom: 1px solid #e0e0e0;
  padding: 12px 16px;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-input {
  padding: 8px 16px;
  background-color: white;
  border-top: 1px solid #e0e0e0;
  display: flex;
  gap: 8px;
}

/* Message styling */
.message-bubble {
  max-width: 80%;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  margin-bottom: 8px;
}

.user {
  align-self: flex-end;
  display: flex;
  justify-content: flex-end;
}

.ai {
  align-self: flex-start;
}

.message-bubble.user {
  background-color: #1976d2;
  color: white;
  border-bottom-right-radius: 4px;
}

.message-bubble.ai {
  background-color: white;
  border-bottom-left-radius: 4px;
}

.message-content {
  word-break: break-word;
}

.timestamp {
  display: block;
  font-size: 0.7rem;
  opacity: 0.7;
  margin-top: 4px;
  text-align: right;
}

/* eBay logo styling */
.ebay-logo {
  font-weight: bold;
  font-size: 1.2rem;
  letter-spacing: -0.5px;
}

.ebay-logo .e {
  color: #e53238;
}

.ebay-logo .b {
  color: #0064d2;
}

.ebay-logo .a {
  color: #f5af02;
}

.ebay-logo .y {
  color: #86b817;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  align-items: center;
  column-gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #bbb;
  border-radius: 50%;
  display: inline-block;
  opacity: 0.4;
  animation: typing 1s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0% {
    transform: translateY(0px);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-5px);
    opacity: 0.8;
  }
  100% {
    transform: translateY(0px);
    opacity: 0.4;
  }
}

/* Transitions */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* Product results styling */
.product-results {
  display: flex;
  flex-direction: column;
}

.product-card {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 8px;
  transition: all 0.2s ease;
}

.product-card:hover {
  background-color: #f0f0f0;
}

.product-image {
  width: 60px;
  height: 60px;
  object-fit: contain;
  border-radius: 4px;
}

.product-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 4px;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.product-price {
  font-weight: 600;
  color: #1976d2;
  font-size: 0.9rem;
}

.product-condition {
  font-size: 0.8rem;
  color: #666;
}

.product-link {
  font-size: 0.8rem;
  color: #1976d2;
  text-decoration: none;
  display: inline-block;
  margin-top: 4px;
}

.product-link:hover {
  text-decoration: underline;
}

/* Login card styling */
.login-card {
  display: flex;
  flex-direction: column;
}

.login-required-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
  background-color: #fff3cd12;
}

.login-btn {
  min-width: 180px;
}

.close-btn {
  margin-left: auto;
}
</style>
