<template>
  <div id="app">
    <!-- Show ChatBox button when embedded (like in an iframe) -->
    <ChatBox v-if="isEmbedded" />
    <!-- Show FullApp when accessed directly -->
    <FullApp v-else />
  </div>
</template>

<script>
import ChatBox from "./components/ChatBox.vue";
import FullApp from "./components/FullApp.vue";

export default {
  components: {
    ChatBox,
    FullApp,
  },
  data() {
    return {
      isEmbedded: false,
    };
  },
  mounted() {
    // Check if the app is embedded (in iframe) or accessed directly
    this.isEmbedded =
      window.self !== window.top ||
      window.location.search.includes("embedded=true");
  },
};
</script>
