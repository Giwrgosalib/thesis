<!-- filepath: frontend/src/components/FullApp.vue -->
<template>
  <v-app>
    <v-app-bar app color="primary" dark>
      <div class="ebay-logo mr-4">
        <span class="e">e</span>
        <span class="b">b</span>
        <span class="a">a</span>
        <span class="y">y</span>
      </div>
      <v-toolbar-title>AI Shopping Assistant</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn v-if="loggedIn" @click="logout" text>
        Logout ({{ ebayUsername }})
      </v-btn>
    </v-app-bar>

    <v-main>
      <v-container fluid class="fill-height">
        <!-- Login Required View -->
        <v-row
          v-if="!loggedIn"
          justify="center"
          align="center"
          class="fill-height"
        >
          <v-col cols="12" md="6" lg="4">
            <v-card class="pa-6 text-center">
              <v-icon size="64" color="warning" class="mb-4"
                >mdi-account-lock</v-icon
              >
              <h2 class="text-h4 mb-4">eBay Login Required</h2>
              <p class="text-body-1 mb-6">
                Please sign in to your eBay account to use the shopping
                assistant.
              </p>
              <v-btn
                @click="initiateEbaySignIn"
                color="primary"
                size="large"
                :loading="authLoading"
                :disabled="authLoading"
              >
                {{ authLoading ? "Redirecting to eBay..." : "Sign in to eBay" }}
              </v-btn>

              <v-alert v-if="authError" type="error" class="mt-4">
                {{ authError }}
              </v-alert>
            </v-card>
          </v-col>
        </v-row>

        <!-- Main Chat Interface -->
        <v-row v-else class="fill-height">
          <v-col cols="12" class="d-flex flex-column">
            <!-- Chat Messages Area -->
            <v-card class="flex-grow-1 d-flex flex-column mb-4">
              <v-card-text class="chat-history flex-grow-1">
                <!-- Welcome Message -->
                <div v-if="showWelcomeMessage" class="ai mb-4">
                  <v-card class="message-bubble ai">
                    <v-card-text>
                      <div
                        v-if="isFirstMessageLoading"
                        class="typing-indicator"
                      >
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <div v-else class="message-content">
                        <p>
                          Hello! How can I assist you with finding products on
                          eBay today?
                        </p>
                        <small class="timestamp">{{
                          welcomeMessageTimestamp
                        }}</small>
                      </div>
                    </v-card-text>
                  </v-card>
                </div>

                <!-- Messages -->
                <div
                  v-for="(message, index) in messages"
                  :key="index"
                  :class="message.sender"
                  class="mb-4"
                >
                  <v-card :class="['message-bubble', message.sender]">
                    <v-card-text>
                      <div class="message-content">
                        <p v-if="!message.isProductResults">
                          {{ message.text }}
                        </p>
                        <div v-else class="product-results">
                          <p class="mb-2">
                            Here are some products that match your search:
                          </p>
                          <v-row>
                            <v-col
                              v-for="(product, idx) in message.products"
                              :key="idx"
                              cols="12"
                              md="6"
                              lg="4"
                            >
                              <v-card class="product-card">
                                <v-img
                                  v-if="product.image && product.image.imageUrl"
                                  :src="product.image.imageUrl"
                                  height="200"
                                  contain
                                ></v-img>
                                <v-card-title class="text-subtitle-1">
                                  {{ product.title }}
                                </v-card-title>
                                <v-card-text>
                                  <div
                                    class="product-price text-h6 text-primary"
                                  >
                                    ${{ product.price.value }}
                                    {{ product.price.currency }}
                                  </div>
                                  <div class="product-condition text-caption">
                                    {{ product.condition }}
                                  </div>
                                </v-card-text>
                                <v-card-actions>
                                  <v-btn
                                    :href="product.publicUrl"
                                    target="_blank"
                                    color="primary"
                                    variant="outlined"
                                    size="small"
                                  >
                                    View on eBay
                                  </v-btn>
                                </v-card-actions>
                              </v-card>
                            </v-col>
                          </v-row>
                        </div>
                        <small class="timestamp">{{ message.timestamp }}</small>
                      </div>
                    </v-card-text>
                  </v-card>
                </div>

                <!-- Typing Indicator -->
                <div v-if="isTyping" class="ai mb-4">
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
              <v-card-actions class="chat-input pa-4">
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
                  class="flex-grow-1 mr-2"
                ></v-text-field>
                <v-btn
                  color="primary"
                  @click="sendMessage"
                  :loading="isLoading"
                >
                  Send
                </v-btn>
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
  },
};
</script>

<style scoped>
/* Move relevant styles from ChatBox here and adapt for full-screen layout */
.chat-history {
  height: 60vh;
  overflow-y: auto;
  padding: 16px;
}

.message-bubble {
  max-width: 70%;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
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
}

.message-bubble.ai {
  background-color: white;
  border: 1px solid #e0e0e0;
}

/* Add other necessary styles */
</style>
