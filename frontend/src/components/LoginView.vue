<template>
  <div
    class="relative w-full h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-white to-slate-100 flex items-center justify-center font-sans"
  >
    <!-- Floating Background Assets -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <!-- Icon 1: Shopping Bag -->
      <div
        class="absolute top-[15%] left-[10%] w-24 h-24 opacity-60 blur-[2px] animate-float-slow"
        style="animation-delay: 0s"
      >
        <img
          :src="icons.shopping"
          alt="Shopping"
          class="w-full h-full drop-shadow-xl"
        />
      </div>

      <!-- Icon 2: Camera -->
      <div
        class="absolute top-[60%] left-[15%] w-20 h-20 opacity-50 blur-[1px] animate-float-medium"
        style="animation-delay: 2s"
      >
        <img
          :src="icons.camera"
          alt="Camera"
          class="w-full h-full drop-shadow-lg"
        />
      </div>

      <!-- Icon 3: Watch/Clock (History) -->
      <div
        class="absolute top-[20%] right-[15%] w-28 h-28 opacity-60 blur-[3px] animate-float-slower"
        style="animation-delay: 1s"
      >
        <img
          :src="icons.history"
          alt="History"
          class="w-full h-full drop-shadow-2xl"
        />
      </div>

      <!-- Icon 4: Robot/AI -->
      <div
        class="absolute bottom-[10%] right-[20%] w-32 h-32 opacity-40 blur-[2px] animate-float-medium"
        style="animation-delay: 3s"
      >
        <img :src="icons.robot" alt="AI" class="w-full h-full drop-shadow-xl" />
      </div>

      <!-- Icon 5: Tag -->
      <div
        class="absolute top-[50%] right-[5%] w-16 h-16 opacity-30 blur-[1px] animate-float-slow"
        style="animation-delay: 4s"
      >
        <img :src="icons.tag" alt="Tag" class="w-full h-full drop-shadow-md" />
      </div>
      <!-- Icon 6: Store -->
      <div
        class="absolute bottom-[20%] left-[5%] w-18 h-18 opacity-40 blur-[2px] animate-float-slower"
        style="animation-delay: 1.5s"
      >
        <img
          :src="icons.store"
          alt="Store"
          class="w-full h-full drop-shadow-lg"
        />
      </div>
    </div>

    <!-- The Glass Login Card -->
    <div
      class="relative z-10 w-full max-w-md p-8 mx-4 bg-white/70 backdrop-blur-xl border border-white/40 rounded-3xl shadow-2xl hover:shadow-3xl transition-shadow duration-500 flex flex-col items-center"
    >
      <!-- Brand Logo -->
      <div class="mb-8 flex items-center gap-1 opacity-90">
        <div class="flex items-center font-extrabold text-2xl tracking-tighter">
          <span class="text-[#e53238]">e</span>
          <span class="text-[#0064d2]">b</span>
          <span class="text-[#f5af02]">a</span>
          <span class="text-[#86b817]">y</span>
          <span class="ml-2 text-slate-800 font-bold text-lg">Scout</span>
        </div>
      </div>

      <!-- Welcome Text -->
      <div class="text-center mb-10 space-y-2">
        <h2 class="text-3xl font-bold text-slate-800 tracking-tight">
          Welcome Back
        </h2>
        <p class="text-slate-500 font-medium">
          Discover a world of products floating around you.
        </p>
      </div>

      <!-- Action Container -->
      <div class="w-full space-y-6">
        <p class="text-center text-slate-500 font-medium px-4">
          Sign in securely via eBay to access your AI shopping assistant.
        </p>

        <!-- OAuth Button (Round White) -->
        <button
          @click="handleLogin"
          class="w-full py-5 bg-white hover:bg-slate-50 rounded-full shadow-2xl shadow-blue-500/10 border border-slate-100 transform hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 flex items-center justify-center gap-3 cursor-pointer group"
          :disabled="isLoading"
        >
          <span
            v-if="isLoading"
            class="w-6 h-6 border-2 border-slate-200 border-t-[#3665F3] rounded-full animate-spin"
          ></span>
          <div v-else class="flex items-center gap-2">
            <div class="flex items-center font-black text-2xl tracking-tighter">
              <span class="text-[#e53238]">e</span>
              <span class="text-[#0064d2]">b</span>
              <span class="text-[#f5af02]">a</span>
              <span class="text-[#86b817]">y</span>
            </div>
            <span
              class="text-slate-800 font-bold text-lg border-l border-slate-200 pl-3"
              >Sign In</span
            >
          </div>
        </button>
      </div>

      <!-- Footer -->
      <div class="mt-8 text-xs text-slate-400 font-medium text-center">
        Powered by <span class="text-slate-600 font-bold">eBay OAuth</span>
      </div>
    </div>
  </div>
</template>

<script>
import { appAuth } from "../services/auth";

// Import icons
import shoppingIcon from "@/assets/icons/shopping.svg";
import cameraIcon from "@/assets/icons/camera.svg";
import historyIcon from "@/assets/icons/history.svg";
import robotIcon from "@/assets/icons/robot.svg";
import tagIcon from "@/assets/icons/tag.svg";
import storeIcon from "@/assets/icons/store.svg";
import ebayIcon from "@/assets/icons/ebay.svg";

export default {
  name: "LoginView",
  data() {
    return {
      isLoading: false,
      icons: {
        shopping: shoppingIcon,
        camera: cameraIcon,
        history: historyIcon,
        robot: robotIcon,
        tag: tagIcon,
        store: storeIcon,
        ebay: ebayIcon,
      },
    };
  },
  methods: {
    async handleLogin() {
      this.isLoading = true;
      // Trigger eBay OAuth flow directly
      appAuth.initiateEbayLogin();
    },
  },
};
</script>

<style scoped>
/* Antigravity Animation */
@keyframes float {
  0%,
  100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-20px);
  }
}

.animate-float-slow {
  animation: float 8s ease-in-out infinite;
}

.animate-float-medium {
  animation: float 6s ease-in-out infinite;
}

.animate-float-slower {
  animation: float 10s ease-in-out infinite;
}
</style>
