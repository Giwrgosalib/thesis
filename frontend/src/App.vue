<template>
  <div id="app">
    <!-- Show ChatBox button when embedded (like in an iframe) -->
    <ChatBox v-if="isEmbedded" />

    <!-- Show Authenticated App -->
    <FullApp v-else-if="loggedIn" @logout="handleLogout" />

    <!-- Show Login View -->
    <LoginView v-else />
  </div>
</template>

<script>
import { appAuth } from "./services/auth";
import ChatBox from "./components/ChatBox.vue";
import FullApp from "./components/FullApp.vue";
import LoginView from "./components/LoginView.vue";

export default {
  components: {
    ChatBox,
    FullApp,
    LoginView,
  },
  data() {
    return {
      isEmbedded: false,
      loggedIn: false,
    };
  },
  async mounted() {
    // Check if the app is embedded (in iframe) or accessed directly
    this.isEmbedded =
      window.self !== window.top ||
      window.location.search.includes("embedded=true");

    // Check for auth return loop
    const returnData = await appAuth.checkForAuthReturn();
    if (returnData.isReturn && returnData.success) {
      this.loggedIn = true;
    } else {
      // Check stored auth
      const stored = appAuth.getStoredAuthData();
      if (stored) {
        this.loggedIn = true;
      }
    }
  },
  methods: {
    handleLogout() {
      this.loggedIn = false;
    },
  },
};
</script>
