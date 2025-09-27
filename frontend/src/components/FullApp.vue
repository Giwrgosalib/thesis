<!-- filepath: frontend/src/components/FullApp.vue -->
<template>
  <v-app class="ebay-chat-app">
    <!-- Modern Header with eBay Branding -->
    <v-app-bar app elevation="0" class="ebay-header">
      <div class="header-content">
        <div class="ebay-logo-container">
          <div class="ebay-logo">
            <span class="e">e</span>
            <span class="b">b</span>
            <span class="a">a</span>
            <span class="y">y</span>
          </div>
          <div class="logo-text">
            <h1 class="app-title">AI Shopping Assistant</h1>
            <p class="app-subtitle">Find the perfect products with AI</p>
          </div>
        </div>

        <div class="header-actions">
          <v-chip
            v-if="loggedIn"
            color="success"
            variant="flat"
            class="user-chip"
          >
            <v-icon start>mdi-account-circle</v-icon>
            {{ ebayUsername }}
          </v-chip>
          <v-btn
            v-if="loggedIn"
            @click="logout"
            variant="outlined"
            color="ebay-red"
            class="logout-btn"
          >
            <v-icon start>mdi-logout</v-icon>
            Logout
          </v-btn>
        </div>
      </div>
    </v-app-bar>

    <v-main>
      <v-container fluid class="fill-height">
        <!-- Modern Login View -->
        <v-row
          v-if="!loggedIn"
          justify="center"
          align="center"
          class="fill-height login-container"
        >
          <v-col cols="12" md="6" lg="5" xl="4">
            <v-card class="login-card" elevation="8">
              <div class="login-header">
                <div class="login-icon">
                  <v-icon size="80" color="ebay-red">mdi-robot</v-icon>
                </div>
                <h2 class="login-title">Welcome to eBay AI Assistant</h2>
                <p class="login-subtitle">
                  Your intelligent shopping companion powered by AI
                </p>
              </div>

              <v-card-text class="login-content">
                <div class="features-list">
                  <div class="feature-item">
                    <v-icon color="ebay-blue" class="feature-icon"
                      >mdi-magnify</v-icon
                    >
                    <span>Smart product search</span>
                  </div>
                  <div class="feature-item">
                    <v-icon color="ebay-yellow" class="feature-icon"
                      >mdi-lightbulb</v-icon
                    >
                    <span>Personalized recommendations</span>
                  </div>
                  <div class="feature-item">
                    <v-icon color="ebay-green" class="feature-icon"
                      >mdi-shield-check</v-icon
                    >
                    <span>Secure eBay integration</span>
                  </div>
                </div>

                <v-btn
                  @click="initiateEbaySignIn"
                  color="ebay-red"
                  size="x-large"
                  class="login-btn"
                  :loading="authLoading"
                  :disabled="authLoading"
                  block
                >
                  <v-icon start>mdi-ebay</v-icon>
                  {{
                    authLoading ? "Connecting to eBay..." : "Sign in with eBay"
                  }}
                </v-btn>

                <v-alert
                  v-if="authError"
                  type="error"
                  class="mt-4"
                  variant="tonal"
                >
                  <v-icon start>mdi-alert-circle</v-icon>
                  {{ authError }}
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Modern Chat Interface -->
        <v-row v-else class="fill-height chat-container">
          <v-col cols="12" class="d-flex flex-column">
            <!-- Chat Messages Area -->
            <v-card class="chat-window" elevation="2">
              <v-card-text class="chat-history">
                <!-- Welcome Message -->
                <div v-if="showWelcomeMessage" class="message-container ai">
                  <div class="message-bubble ai">
                    <div class="message-avatar">
                      <v-avatar size="32" color="ebay-red">
                        <v-icon color="white">mdi-robot</v-icon>
                      </v-avatar>
                    </div>
                    <div class="message-content">
                      <div
                        v-if="isFirstMessageLoading"
                        class="typing-indicator"
                      >
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <div v-else class="message-text">
                        <p class="welcome-text">
                          👋 Hello! I'm your eBay AI shopping assistant. I can
                          help you find the perfect products with smart search
                          and personalized recommendations.
                        </p>
                        <div class="suggestion-chips">
                          <v-chip
                            v-for="suggestion in quickSuggestions"
                            :key="suggestion"
                            @click="sendSuggestion(suggestion)"
                            variant="outlined"
                            color="ebay-blue"
                            class="suggestion-chip"
                          >
                            {{ suggestion }}
                          </v-chip>
                        </div>
                        <small class="timestamp">{{
                          welcomeMessageTimestamp
                        }}</small>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Chat Messages -->
                <div
                  v-for="(message, index) in messages"
                  :key="index"
                  :class="['message-container', message.sender]"
                >
                  <div :class="['message-bubble', message.sender]">
                    <div class="message-avatar">
                      <v-avatar
                        v-if="message.sender === 'ai'"
                        size="32"
                        color="ebay-red"
                      >
                        <v-icon color="white">mdi-robot</v-icon>
                      </v-avatar>
                      <v-avatar v-else size="32" color="ebay-blue">
                        <v-icon color="white">mdi-account</v-icon>
                      </v-avatar>
                    </div>
                    <div class="message-content">
                      <div class="message-text">
                        <p v-if="!message.isProductResults">
                          {{ message.text }}
                        </p>
                        <div v-else class="product-results">
                          <p class="results-header">
                            🛍️ Here are some products that match your search:
                          </p>
                          <div class="products-grid">
                            <v-card
                              v-for="(product, idx) in message.products"
                              :key="idx"
                              class="product-card"
                              elevation="2"
                            >
                              <div class="product-image-container">
                                <v-img
                                  v-if="product.image && product.image.imageUrl"
                                  :src="product.image.imageUrl"
                                  height="180"
                                  cover
                                  class="product-image"
                                >
                                  <template v-slot:placeholder>
                                    <div class="image-placeholder">
                                      <v-icon size="48" color="grey-lighten-2"
                                        >mdi-image</v-icon
                                      >
                                    </div>
                                  </template>
                                </v-img>
                                <div v-else class="image-placeholder">
                                  <v-icon size="48" color="grey-lighten-2"
                                    >mdi-image</v-icon
                                  >
                                </div>
                              </div>

                              <v-card-title class="product-title">
                                {{ product.title }}
                              </v-card-title>

                              <v-card-text class="product-details">
                                <div class="product-price">
                                  <span class="price-currency">{{
                                    product.price.currency
                                  }}</span>
                                  <span class="price-value">{{
                                    product.price.value
                                  }}</span>
                                </div>
                                <v-chip
                                  :color="getConditionColor(product.condition)"
                                  size="small"
                                  variant="flat"
                                  class="condition-chip"
                                >
                                  {{ product.condition }}
                                </v-chip>
                              </v-card-text>

                              <v-card-actions class="product-actions">
                                <v-btn
                                  :href="product.publicUrl"
                                  target="_blank"
                                  color="ebay-red"
                                  variant="flat"
                                  size="small"
                                  class="view-btn"
                                >
                                  <v-icon start>mdi-open-in-new</v-icon>
                                  View on eBay
                                </v-btn>
                              </v-card-actions>
                            </v-card>
                          </div>
                        </div>
                        <small class="timestamp">{{ message.timestamp }}</small>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Typing Indicator -->
                <div v-if="isTyping" class="message-container ai">
                  <div class="message-bubble ai">
                    <div class="message-avatar">
                      <v-avatar size="32" color="ebay-red">
                        <v-icon color="white">mdi-robot</v-icon>
                      </v-avatar>
                    </div>
                    <div class="message-content">
                      <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                </div>
              </v-card-text>

              <!-- Modern Input Area -->
              <v-card-actions class="chat-input">
                <div class="input-container">
                  <v-textarea
                    v-model="userInput"
                    placeholder="Ask me anything about products on eBay..."
                    variant="outlined"
                    hide-details
                    color="ebay-blue"
                    auto-grow
                    rows="1"
                    max-rows="4"
                    @keydown.enter.prevent="handleEnterKey"
                    :disabled="isLoading"
                    class="message-input"
                  ></v-textarea>
                  <v-btn
                    color="ebay-red"
                    @click="sendMessage"
                    :loading="isLoading"
                    :disabled="!userInput.trim()"
                    class="send-btn"
                    size="large"
                  >
                    <v-icon>mdi-send</v-icon>
                  </v-btn>
                </div>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script>
import { appAuth } from "../services/auth.js";

export default {
  name: "FullApp",
  data() {
    return {
      userInput: "",
      messages: [],
      isTyping: false,
      isLoading: false,
      showWelcomeMessage: false,
      isFirstMessageLoading: true,
      welcomeMessageTimestamp: "",

      // Quick suggestions for new users
      quickSuggestions: [
        "iPhone 15 Pro under $1000",
        "Gaming laptop with RTX 4060",
        "Nike running shoes size 10",
        "MacBook Air 2023",
        "Sony headphones wireless",
      ],

      // Authentication State
      loggedIn: false,
      userId: null,
      appSessionToken: null,
      ebayUsername: null,
      authError: "",
      authLoading: false,
      authCheckLoading: true,
      clientId: null,
    };
  },

  async mounted() {
    this.authCheckLoading = true;
    console.log("FullApp mounted");

    // Check if we just returned from eBay auth
    const authReturn = await appAuth.checkForAuthReturn();

    if (authReturn.isReturn) {
      if (authReturn.success && authReturn.authData) {
        console.log("Successfully returned from eBay auth");
        this.setAuthData(authReturn.authData);
      } else if (authReturn.error) {
        this.authError = `Authentication failed: ${authReturn.error}`;
        this.authLoading = false;
      }
    } else {
      // Check localStorage for existing auth data
      await this.checkStoredAuth();
    }

    if (this.loggedIn && !this.showWelcomeMessage) {
      this.showWelcomeMessage = true;
      this.simulateFirstMessageLoading();
    }

    this.authCheckLoading = false;
  },

  beforeUnmount() {
    // Clean up any intervals if needed
  },

  methods: {
    // Set authentication data in component and localStorage
    setAuthData(authData) {
      this.loggedIn = true;
      this.appSessionToken = authData.sessionToken;
      this.userId = authData.userId;
      this.ebayUsername = authData.ebayUsername;
      this.authError = "";
      this.authLoading = false;

      console.log("User authenticated:", {
        userId: this.userId,
        ebayUsername: this.ebayUsername,
      });
    },

    // Check localStorage for stored authentication
    async checkStoredAuth() {
      const storedAuth = appAuth.getStoredAuthData();

      if (storedAuth) {
        console.log("Found stored auth data, validating...");

        // Validate the stored token with backend
        const status = await appAuth.checkStatus(storedAuth.sessionToken);

        if (status.authenticated) {
          this.setAuthData(storedAuth);
          console.log("Stored session is valid");
        } else {
          console.log("Stored session is invalid, clearing...");
          appAuth.clearStoredAuthData();
          this.loggedIn = false;
          this.authError = "Your session has expired. Please sign in again.";
        }
      } else {
        console.log("No stored auth data found");
        this.loggedIn = false;
      }
    },

    async initiateEbaySignIn() {
      this.authLoading = true;
      this.authError = "";

      // Check API health
      const healthCheck = await appAuth.checkApiHealth();
      if (healthCheck.status !== "ok") {
        this.authError = `API connection error: ${healthCheck.message}`;
        this.authLoading = false;
        return;
      }

      // Generate a new client ID
      this.clientId = "client_" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("authClientId", this.clientId);

      console.log("Initiating eBay sign-in with clientId:", this.clientId);

      // Redirect to eBay OAuth
      appAuth.initiateEbayLogin(this.clientId);
    },

    async logout() {
      if (this.appSessionToken) {
        await appAuth.logout(this.appSessionToken);
      }

      // Clear component state
      this.loggedIn = false;
      this.userId = null;
      this.appSessionToken = null;
      this.ebayUsername = null;
      this.messages = [];
      this.showWelcomeMessage = false;
      this.authError = "";
      this.authCheckLoading = false;

      console.log("User logged out");
    },

    async sendMessage() {
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
        const requestBody = { query: query };
        const headers = {
          "Content-Type": "application/json",
        };

        if (this.loggedIn && this.appSessionToken) {
          headers["Authorization"] = `Bearer ${this.appSessionToken}`;
        } else {
          console.warn("Sending search query without authentication");
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

    // Handle Enter key for sending messages
    handleEnterKey(event) {
      if (event.shiftKey) {
        // Allow new line with Shift+Enter
        return;
      }
      // Send message with Enter
      event.preventDefault();
      this.sendMessage();
    },

    // Send suggestion as message
    sendSuggestion(suggestion) {
      this.userInput = suggestion;
      this.sendMessage();
    },

    // Get condition color for product chips
    getConditionColor(condition) {
      const conditionColors = {
        New: "success",
        Used: "warning",
        Refurbished: "info",
        "Like New": "success",
        Good: "primary",
        Fair: "orange",
        Acceptable: "grey",
      };
      return conditionColors[condition] || "grey";
    },
  },
};
</script>

<style scoped>
/* eBay Color Palette */
:root {
  --ebay-red: #e53238;
  --ebay-blue: #0064d2;
  --ebay-yellow: #f5af02;
  --ebay-green: #86b817;
  --ebay-dark: #2c2c2c;
  --ebay-light: #f8f9fa;
  --ebay-border: #e1e5e9;
}

/* Global App Styles */
.ebay-chat-app {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  min-height: 100vh;
}

/* Header Styles */
.ebay-header {
  background: white !important;
  border-bottom: 1px solid var(--ebay-border);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.ebay-logo-container {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ebay-logo {
  font-weight: bold;
  font-size: 2rem;
  letter-spacing: -1px;
  display: flex;
  gap: 2px;
}

.ebay-logo .e {
  color: var(--ebay-red);
}
.ebay-logo .b {
  color: var(--ebay-blue);
}
.ebay-logo .a {
  color: var(--ebay-yellow);
}
.ebay-logo .y {
  color: var(--ebay-green);
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.app-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--ebay-dark);
  margin: 0;
  line-height: 1.2;
}

.app-subtitle {
  font-size: 0.875rem;
  color: #6c757d;
  margin: 0;
  line-height: 1.2;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-chip {
  background: var(--ebay-green) !important;
  color: white !important;
}

.logout-btn {
  border-color: var(--ebay-red) !important;
  color: var(--ebay-red) !important;
}

/* Login Styles */
.login-container {
  background: linear-gradient(135deg, var(--ebay-light) 0%, #ffffff 100%);
  padding: 40px 20px;
}

.login-card {
  border-radius: 16px !important;
  overflow: hidden;
  background: white;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  padding: 40px 32px 24px;
  background: linear-gradient(135deg, var(--ebay-red) 0%, #c62828 100%);
  color: white;
}

.login-icon {
  margin-bottom: 16px;
}

.login-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.login-subtitle {
  font-size: 1rem;
  opacity: 0.9;
  margin: 0;
}

.login-content {
  padding: 32px !important;
}

.features-list {
  margin-bottom: 32px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  font-size: 1rem;
  color: var(--ebay-dark);
}

.feature-icon {
  font-size: 1.25rem;
}

.login-btn {
  background: var(--ebay-red) !important;
  color: white !important;
  font-weight: 600;
  font-size: 1.1rem;
  padding: 16px !important;
  border-radius: 8px !important;
}

/* Chat Container */
.chat-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.chat-window {
  border-radius: 16px !important;
  overflow: hidden;
  background: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #fafbfc;
}

/* Message Styles */
.message-container {
  margin-bottom: 20px;
  display: flex;
}

.message-container.user {
  justify-content: flex-end;
}

.message-container.ai {
  justify-content: flex-start;
}

.message-bubble {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 70%;
  padding: 16px 20px;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message-bubble.user {
  background: linear-gradient(135deg, var(--ebay-blue) 0%, #0056b3 100%);
  color: white;
  flex-direction: row-reverse;
}

.message-bubble.ai {
  background: white;
  border: 1px solid var(--ebay-border);
  color: var(--ebay-dark);
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-text p {
  margin: 0 0 8px 0;
  line-height: 1.5;
  word-wrap: break-word;
}

.welcome-text {
  font-size: 1rem;
  margin-bottom: 16px !important;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.suggestion-chip {
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestion-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 100, 210, 0.3);
}

.timestamp {
  color: #6c757d;
  font-size: 0.75rem;
  margin-top: 8px;
  display: block;
}

/* Typing Indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ebay-blue);
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}

/* Product Results */
.product-results {
  margin-top: 8px;
}

.results-header {
  font-weight: 600;
  margin-bottom: 16px !important;
  color: var(--ebay-dark);
}

.products-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.product-card {
  border-radius: 12px !important;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid var(--ebay-border);
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.product-image-container {
  position: relative;
  background: #f8f9fa;
}

.product-image {
  transition: transform 0.3s ease;
}

.product-card:hover .product-image {
  transform: scale(1.05);
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 180px;
  background: #f8f9fa;
}

.product-title {
  font-size: 0.95rem !important;
  font-weight: 600 !important;
  line-height: 1.3 !important;
  padding: 12px 16px 8px !important;
  color: var(--ebay-dark) !important;
}

.product-details {
  padding: 0 16px 12px !important;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.product-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.price-currency {
  font-size: 0.875rem;
  color: #6c757d;
}

.price-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ebay-red);
}

.condition-chip {
  font-size: 0.75rem !important;
}

.product-actions {
  padding: 0 16px 16px !important;
}

.view-btn {
  width: 100%;
  font-weight: 600;
}

/* Input Area */
.chat-input {
  padding: 20px 24px !important;
  background: white;
  border-top: 1px solid var(--ebay-border);
}

.input-container {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  width: 100%;
}

.message-input {
  flex: 1;
}

.message-input :deep(.v-field) {
  border-radius: 24px !important;
  border-color: var(--ebay-border) !important;
}

.message-input :deep(.v-field--focused) {
  border-color: var(--ebay-blue) !important;
  box-shadow: 0 0 0 2px rgba(0, 100, 210, 0.1) !important;
}

.send-btn {
  border-radius: 50% !important;
  min-width: 48px !important;
  height: 48px !important;
  background: var(--ebay-red) !important;
  color: white !important;
}

.send-btn:disabled {
  background: #e9ecef !important;
  color: #6c757d !important;
}

/* Responsive Design */
@media (max-width: 768px) {
  .header-content {
    padding: 0 16px;
  }

  .logo-text {
    display: none;
  }

  .chat-container {
    padding: 12px;
  }

  .chat-window {
    height: calc(100vh - 100px);
  }

  .chat-history {
    padding: 16px;
  }

  .message-bubble {
    max-width: 85%;
    padding: 12px 16px;
  }

  .products-grid {
    grid-template-columns: 1fr;
  }

  .login-content {
    padding: 24px !important;
  }
}

@media (max-width: 480px) {
  .ebay-logo {
    font-size: 1.5rem;
  }

  .app-title {
    font-size: 1.25rem;
  }

  .message-bubble {
    max-width: 90%;
    padding: 10px 14px;
  }

  .chat-input {
    padding: 16px !important;
  }
}
</style>
