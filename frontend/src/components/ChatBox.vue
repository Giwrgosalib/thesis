<!-- eslint-disable prettier/prettier -->
<template>
  <!-- Only the button is visible - opens app in new tab -->
  <v-btn
    class="chat-fab hover:scale-105 transition-transform duration-200"
    @click="openAppInNewTab"
  >
    <div class="ebay-logo">
      <span class="e">e</span>
      <span class="b">b</span>
      <span class="a">a</span>
      <span class="y">y</span>
    </div>
  </v-btn>
</template>

<script>
export default {
  name: "ChatBox",
  methods: {
    openAppInNewTab() {
      // Open the full app in a new tab
      const appUrl = window.location.origin; // This will be your app's base URL
      window.open(appUrl, "_blank");
    },
  },
};
</script>

<style scoped>
/* Keep only the FAB button styling */
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
</style>
