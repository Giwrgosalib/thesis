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
        <v-btn @click="handleLogin" class="login-btn">
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
import { ebayAuth } from "../services/auth.js"; // Import your eBay authentication module
export default {
  name: "ChatBox",
  data() {
    return {
      userInput: "",
      messages: [],
      isChatOpen: false,
      isTyping: false,
      isLoading: false,
      showWelcomeMessage: false, // Controls visibility of the welcome message
      isFirstMessageLoading: true, // Controls loading state for the first message
      welcomeMessageTimestamp: "", // Timestamp for the welcome message
      apiBaseUrl: "http://localhost:5000", // Base URL for API
      userId: null, // Add userId property
      loggedIn: false, // Add loggedIn property
    };
  },
  mounted() {
    this.checkEbayLoginStatus();
  },
  methods: {
    async sendMessage() {
      if (this.userInput.trim() === "") return;

      // Add user's message
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
        // Prepare request body, including userId if available
        const requestBody = {
          query: query,
        };
        if (this.userId) {
          requestBody.userId = this.userId; // Add userId to the request body
        }

        const response = await fetch(`${this.apiBaseUrl}/search`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          // Send the body including the userId
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`Server responded with status: ${response.status}`);
        }

        const data = await response.json();

        // Handle response (same as before)
        if (data && data.length > 0) {
          // Assuming backend returns a list directly now
          this.messages.push({
            sender: "ai",
            isProductResults: true,
            products: data.slice(0, 5), // Show top 5 results
            text: `I found some products matching your search.`, // Adjusted text
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
          text: "Sorry, I encountered an error while searching. Please try again later.",
          timestamp: this.getCurrentTimestamp(),
        });
      } finally {
        this.isTyping = false;
        this.isLoading = false;
      }
    },

    toggleChat() {
      this.isChatOpen = !this.isChatOpen;
      if (this.isChatOpen) {
        // Update login status when opening the chat.
        // this.checkEbayLoginStatus() will set this.loggedIn and this.userId,
        // and also handle showing the welcome message if the user is logged in.
        this.checkEbayLoginStatus();
      }
    },

    getCurrentTimestamp() {
      const now = new Date();
      return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    },

    simulateFirstMessageLoading() {
      setTimeout(() => {
        this.isFirstMessageLoading = false;
        this.welcomeMessageTimestamp = this.getCurrentTimestamp();
      }, 1000);
    },

    handleLogin() {
      ebayAuth.initiateLogin();
      // The page will redirect to eBay, then back to your app
    },

    async checkEbayLoginStatus() {
      try {
        // Directly fetch status and user data in one call
        const response = await fetch(`${this.apiBaseUrl}/auth/status`, {
          credentials: "include", // Ensures cookies are sent
        });

        if (!response.ok) {
          this.loggedIn = false;
          this.userId = null;
          return; // Exit if the request failed
        }

        const data = await response.json();
        this.loggedIn = data.authenticated;

        if (this.loggedIn) {
          this.userId = data.userId;
          console.log("User logged in with ID:", this.userId);

          if (this.isChatOpen && !this.showWelcomeMessage) {
            this.showWelcomeMessage = true;
            this.simulateFirstMessageLoading();
          }
        } else {
          this.userId = null;
        }
      } catch (error) {
        console.error("Error in checkEbayLoginStatus:", error);
        this.loggedIn = false;
        this.userId = null;
      }
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
