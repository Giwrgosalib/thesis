<template>
  <!-- Only the button is visible - opens app in new tab -->
  <button
    class="chat-fab hover:scale-110 active:scale-95 transition-all duration-300 flex items-center justify-center cursor-pointer group"
    @click="openAppInNewTab"
  >
    <div class="flex items-center font-black text-lg tracking-tighter">
      <span class="text-[#e53238]">e</span>
      <span class="text-[#0064d2]">b</span>
      <span class="text-[#f5af02]">a</span>
      <span class="text-[#86b817]">y</span>
    </div>
  </button>
</template>

<script>
export default {
  name: "ChatBox",
  methods: {
    openAppInNewTab() {
      // Open the full app in a new tab
      const appUrl = window.location.origin;
      window.open(appUrl, "_blank");
    },
  },
};
</script>

<style scoped>
.chat-fab {
  position: fixed;
  bottom: 24px;
  left: 24px;
  z-index: 9999;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background-color: white;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
}

.chat-fab:hover {
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
}
</style>
