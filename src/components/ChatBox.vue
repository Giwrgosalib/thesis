<template>
  <div>
    <!-- Floating Button -->
    <v-btn
      fab
      dark
      color="grey lighten-2"
      class="chat-fab hover:scale-105 transition-transform duration-200"
      @click="toggleChat"
    >
      <!-- eBay Logo as Text -->
      <div class="ebay-logo">
        <span class="e">e</span>
        <span class="b">b</span>
        <span class="a">a</span>
        <span class="y">y</span>
      </div>
    </v-btn>

    <!-- Chat Widget -->
    <v-slide-y-transition>
      <v-card v-if="isChatOpen" class="chat-card">
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
                <div class="message-content">
                  <p>Hello! How can I assist you today?</p>
                  <small class="timestamp">{{ getCurrentTimestamp() }}</small>
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
                  <p>{{ message.text }}</p>
                  <small class="timestamp">{{ message.timestamp }}</small>
                </div>
              </v-card-text>
            </v-card>
          </div>

          <!-- Typing Indicator -->
          <div v-if="isTyping" class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
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
    </v-slide-y-transition>
  </div>
</template>

<script>
export default {
  data() {
    return {
      userInput: "",
      messages: [],
      isChatOpen: false,
      isTyping: false,
      isLoading: false,
      showWelcomeMessage: false, // Controls visibility of the welcome message
    };
  },
  methods: {
    async sendMessage() {
      if (this.userInput.trim() === "") return;

      // Add user's message to chat history
      this.messages.push({
        sender: "user",
        text: this.userInput,
        timestamp: this.getCurrentTimestamp(), // Add timestamp
      });

      // Clear input
      this.userInput = "";

      // Simulate AI typing
      this.isTyping = true;
      this.isLoading = true;

      // Simulate API call delay
      setTimeout(async () => {
        try {
          const response = await this.$axios.post(
            "http://localhost:5000/api/recommendations",
            {
              query: this.userInput,
            }
          );

          // Add AI's response to chat history
          this.messages.push({
            sender: "ai",
            text: response.data.recommendations,
            timestamp: this.getCurrentTimestamp(), // Add timestamp
          });
        } catch (error) {
          console.error("Error fetching recommendations:", error);
          this.messages.push({
            sender: "ai",
            text: "Sorry, something went wrong. Please try again.",
            timestamp: this.getCurrentTimestamp(), // Add timestamp
          });
        }

        // Reset states
        this.isTyping = false;
        this.isLoading = false;
      }, 1500); // Simulate a 1.5-second delay
    },
    toggleChat() {
      this.isChatOpen = !this.isChatOpen;
      if (this.isChatOpen && !this.showWelcomeMessage) {
        // Show welcome message only once when the chat is opened
        this.showWelcomeMessage = true;
      }
    },
    getCurrentTimestamp() {
      // Get current time in HH:MM format
      const now = new Date();
      return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    },
  },
};
</script>
