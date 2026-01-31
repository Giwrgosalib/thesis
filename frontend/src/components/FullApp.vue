<template>
  <div class="flex h-screen w-full bg-slate-50 font-sans overflow-hidden">
    <!-- Onboarding Modal (Preserved Logic) -->
    <OnboardingModal v-if="userId" :userId="userId" />

    <!-- LEFT PANEL: Chat Stream (35% width on desktop) -->
    <div
      class="flex flex-col w-full md:w-[35%] h-full bg-white border-r border-gray-200 shadow-md z-10"
      :class="{ 'hidden md:flex': showMobileShowcase }"
    >
      <!-- Header -->
      <header
        class="flex items-center justify-between px-6 py-4 bg-white/90 backdrop-blur-sm sticky top-0 z-20 border-b border-gray-100"
      >
        <div class="flex items-center gap-2">
          <!-- Logo -->
          <div
            class="flex items-center font-extrabold text-2xl tracking-tighter"
          >
            <span class="text-[#e53238]">e</span>
            <span class="text-[#0064d2]">b</span>
            <span class="text-[#f5af02]">a</span>
            <span class="text-[#86b817]">y</span>
            <span class="ml-2 text-slate-800 font-bold text-lg">Scout</span>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- AI Status -->
          <div
            v-if="loggedIn"
            class="flex items-center gap-1.5 px-3 py-1 bg-green-50 text-green-700 text-xs font-semibold rounded-full border border-green-100"
          >
            <span class="relative flex h-2 w-2">
              <span
                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"
              ></span>
              <span
                class="relative inline-flex rounded-full h-2 w-2 bg-green-500"
              ></span>
            </span>
            Active
          </div>

          <!-- Header Actions (Reset, Logout, etc - simplified) -->
          <!-- Header Actions (Reset, Logout) -->
          <div class="flex items-center gap-2">
            <!-- Reset Chat (Always Visible) -->
            <button
              @click="confirmResetChat"
              class="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-full transition-colors"
              title="Reset Chat"
            >
              <v-img :src="icons.refresh" width="18" height="18"></v-img>
            </button>

            <!-- Logout (If Logged In) -->
            <button
              v-if="loggedIn"
              @click="confirmLogout"
              class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors"
              title="Sign Out"
            >
              <v-img :src="icons.logout" width="18" height="18"></v-img>
            </button>

            <!-- Sign In (If Not Logged In) -->
            <button
              v-else
              @click="initiateEbaySignIn"
              class="px-4 py-1.5 bg-[#3665f3] text-white text-xs font-bold rounded-full hover:bg-blue-700 transition-colors shadow-sm"
            >
              Sign In
            </button>
          </div>
        </div>
      </header>

      <!-- Message List -->
      <div
        ref="chatHistoryRef"
        class="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
      >
        <!-- Welcome Message -->
        <div v-if="showWelcomeMessage" class="flex gap-3">
          <div
            class="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 flex items-center justify-center border border-red-200"
          >
            <v-img :src="icons.aiAvatar" width="20" height="20"></v-img>
          </div>
          <div class="flex flex-col gap-2 max-w-[85%]">
            <div
              class="bg-gray-100 p-4 rounded-2xl rounded-tl-sm text-gray-800 text-sm leading-relaxed shadow-sm"
            >
              <p class="font-semibold mb-1">Hi there! 👋</p>
              <p>
                I'm Scout, your advanced AI shopping assistant powered by
                <strong>Hybrid Neural Networks</strong>.
              </p>
            </div>
            <!-- Caps Tags -->
            <div
              class="flex flex-wrap gap-2 text-[10px] font-medium text-gray-500"
            >
              <span class="px-2 py-1 bg-blue-50 text-blue-600 rounded-md"
                >Smart Search</span
              >
              <span class="px-2 py-1 bg-green-50 text-green-600 rounded-md"
                >Enhanced NER</span
              >
            </div>
          </div>
        </div>

        <!-- Chat Loop -->
        <div
          v-for="(msg, idx) in formattedMessages"
          :key="idx"
          class="flex w-full"
          :class="msg.sender === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- Avatar for AI -->
          <div
            v-if="msg.sender === 'ai'"
            class="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 flex items-center justify-center border border-red-200 mr-3 mt-1"
          >
            <v-img :src="icons.aiAvatar" width="20" height="20"></v-img>
          </div>

          <!-- Message Bubble -->
          <div
            class="max-w-[85%] p-3.5 rounded-2xl text-[15px] leading-relaxed shadow-sm relative group cursor-pointer transition-all"
            :class="[
              msg.sender === 'user'
                ? 'bg-[#3665F3] text-white rounded-tr-sm'
                : 'bg-gray-100 text-gray-800 rounded-tl-sm hover:bg-gray-200',
            ]"
            @click="msg.isProductResults ? setActiveShowcase(msg) : null"
          >
            <!-- Text Content -->
            <div v-if="!msg.isProductResults && msg.text">
              {{ msg.text }}
            </div>

            <!-- Typing Indicator (If empty text/loading) -->
            <div
              v-else-if="!msg.isProductResults && !msg.text"
              class="flex gap-1 p-1"
            >
              <span
                class="w-1.5 h-1.5 bg-current rounded-full animate-bounce"
              ></span>
              <span
                class="w-1.5 h-1.5 bg-current rounded-full animate-bounce delay-100"
              ></span>
              <span
                class="w-1.5 h-1.5 bg-current rounded-full animate-bounce delay-200"
              ></span>
            </div>

            <!-- Product Result Summary in Chat (Click to View) -->
            <div v-if="msg.isProductResults" class="flex flex-col gap-2">
              <p class="text-sm border-b border-gray-300/20 pb-2 mb-1">
                {{ msg.text }}
              </p>
              <div
                class="flex items-center gap-2 text-xs font-semibold opacity-80"
              >
                <v-img
                  :src="icons.sparkles"
                  width="14"
                  height="14"
                  class="opacity-70"
                ></v-img>
                <span>Found {{ msg.products.length }} items</span>
              </div>
              <button
                class="mt-1 text-xs bg-white/90 text-gray-900 px-3 py-1.5 rounded-full shadow-sm font-medium hover:bg-white self-start"
              >
                View Results →
              </button>
            </div>

            <!-- Entities Chips (AI Only) -->
            <div
              v-if="
                msg.entitiesSummary &&
                msg.entitiesSummary.length > 0 &&
                msg.sender === 'ai'
              "
              class="mt-3 flex flex-wrap gap-1.5 opacity-90"
            >
              <span
                v-for="(entity, eI) in msg.entitiesSummary"
                :key="eI"
                class="text-[10px] bg-white/50 border border-black/5 px-2 py-0.5 rounded text-current"
              >
                {{ entity.label }}: {{ entity.values.join(", ") }}
              </span>
            </div>
          </div>

          <!-- Avatar for User (Optional, right side) -->
          <!-- <div v-if="msg.sender === 'user'" class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 ml-3 mt-1"></div> -->
        </div>
      </div>

      <!-- Input Area (Fixed Bottom) -->
      <div class="p-4 bg-white border-t border-gray-100">
        <!-- Smart Chips -->
        <div class="flex gap-2 mb-3 overflow-x-auto no-scrollbar pb-1">
          <button
            v-for="sug in quickSuggestions"
            :key="sug"
            @click="sendSuggestion(sug)"
            class="whitespace-nowrap px-3 py-1.5 text-xs font-medium bg-gray-50 text-gray-600 rounded-full border border-gray-200 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition-colors"
          >
            {{ sug }}
          </button>
        </div>

        <!-- Input Box -->
        <div class="relative flex items-center">
          <textarea
            v-model="userInput"
            rows="1"
            @keydown.enter.prevent="handleEnterKey"
            placeholder="Ask Scout anything..."
            class="w-full pl-5 pr-14 py-3.5 bg-white border border-gray-200 rounded-full text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-lg shadow-gray-100 resize-none overflow-hidden"
            style="min-height: 48px; max-height: 120px"
          ></textarea>

          <div class="absolute right-2 flex items-center gap-1">
            <!-- Send Button (No Spinner, just disabled) -->
            <button
              @click="sendMessage"
              :disabled="!userInput.trim() || isLoading"
              class="p-2 bg-[#3665F3] text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform active:scale-95 shadow-md flex items-center justify-center w-9 h-9"
            >
              <v-img
                :src="icons.send"
                width="16"
                height="16"
                class="filter invert brightness-0"
              ></v-img>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- RIGHT PANEL: Dynamic Showcase (65% width) -->
    <div
      class="hidden md:flex flex-col w-[65%] h-full bg-[#f8f9fa] overflow-hidden relative"
    >
      <!-- Empty State (No products yet) -->
      <div
        v-if="!activeShowcaseProducts || activeShowcaseProducts.length === 0"
        class="flex flex-col items-center justify-center h-full text-gray-400"
      >
        <div
          class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4"
        >
          <v-img
            :src="icons.search"
            width="32"
            height="32"
            class="opacity-30"
          ></v-img>
        </div>
        <p class="text-sm font-medium">Search for products to see them here</p>
      </div>

      <!-- Content State -->
      <div v-else class="h-full flex flex-col">
        <!-- Showcase Header -->
        <div class="px-8 py-6 flex items-center justify-between">
          <div>
            <h2 class="text-2xl font-bold text-gray-900 tracking-tight">
              Top Picks for You
            </h2>
            <p class="text-sm text-gray-500 mt-1">
              Based on your preferences and search
            </p>
          </div>
          <div class="flex gap-2">
            <!-- Filter/Sort Buttons Placeholder -->
            <button
              @click="toggleSort"
              class="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 flex items-center gap-1"
            >
              <v-img
                :src="icons.chart"
                width="14"
                height="14"
                class="opacity-60"
              ></v-img>
              <span>Sort: {{ sortLabel }}</span>
            </button>
          </div>
        </div>

        <!-- Grid Layout -->
        <div class="flex-1 overflow-y-auto px-8 pb-8 custom-scrollbar">
          <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <div
              v-for="(product, idx) in activeShowcaseProducts"
              :key="idx"
              class="group bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex flex-col h-full"
            >
              <!-- Image Area -->
              <div class="relative aspect-[4/3] bg-gray-50 overflow-hidden">
                <a
                  :href="product.itemWebUrl || product.item_url || '#'"
                  target="_blank"
                  class="block w-full h-full"
                >
                  <img
                    :src="getPrimaryImage(product)"
                    @error="handleImageError(product)"
                    class="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-500"
                  />
                </a>
                <!-- Badges Overlay -->
                <div
                  class="absolute top-3 left-3 flex flex-col gap-2 items-start"
                >
                  <span
                    v-if="
                      product.condition &&
                      product.condition.toLowerCase().includes('new')
                    "
                    class="bg-green-500 text-white text-[10px] font-bold px-2 py-1 rounded shadow-sm"
                  >
                    NEW
                  </span>
                  <div
                    v-if="product.reasoning"
                    class="bg-purple-600/90 backdrop-blur-md text-white px-2.5 py-1 rounded-lg text-[10px] font-semibold shadow-sm flex items-center gap-1"
                  >
                    <v-img
                      :src="icons.sparkles"
                      width="12"
                      height="12"
                      class="filter invert brightness-0"
                    ></v-img>
                    <span>{{ product.reasoning }}</span>
                  </div>
                </div>
              </div>

              <!-- Details -->
              <div class="p-4 flex flex-col flex-1">
                <div class="flex justify-between items-start mb-2">
                  <a
                    :href="product.itemWebUrl || product.item_url || '#'"
                    target="_blank"
                    class="hover:underline"
                  >
                    <h3
                      class="font-bold text-gray-900 text-sm leading-snug line-clamp-2 pr-2"
                      :title="product.title"
                    >
                      {{ truncateText(product.title, 60) }}
                    </h3>
                  </a>
                </div>

                <div class="mt-auto pt-3">
                  <div class="flex items-baseline gap-1 mb-1">
                    <span class="text-lg font-extrabold text-[#111820]">{{
                      formatPrice(product.price)
                    }}</span>
                    <span
                      v-if="product.bidCount"
                      class="text-xs text-gray-500 font-medium"
                      >{{ product.bidCount }} bids</span
                    >
                  </div>

                  <div class="flex items-center justify-between">
                    <span
                      class="text-[11px] font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded"
                    >
                      {{ product.condition || "Pre-owned" }}
                    </span>

                    <!-- Hover Action (Action: View Details) -->
                    <a
                      :href="product.itemWebUrl || product.item_url || '#'"
                      target="_blank"
                      class="opacity-0 group-hover:opacity-100 transition-opacity text-xs font-bold text-blue-600 hover:text-blue-700 flex items-center"
                    >
                      Details
                      <v-img
                        :src="icons.arrowRight"
                        width="14"
                        height="14"
                        class="ml-1"
                      ></v-img>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Infinite Scroll Sentinel & Loader -->
          <div
            v-if="hasMoreResults && activeShowcaseProducts.length > 0"
            ref="scrollSentinel"
            class="flex items-center justify-center py-10"
          >
            <div v-if="isLoadingMore" class="flex flex-col items-center gap-3">
              <div class="relative w-10 h-10">
                <div
                  class="absolute inset-0 border-4 border-blue-50 border-solid rounded-full"
                ></div>
                <div
                  class="absolute inset-0 border-4 border-blue-600 border-solid rounded-full border-t-transparent animate-spin"
                ></div>
              </div>
              <span
                class="text-xs font-bold text-slate-400 tracking-widest uppercase"
                >Fetching More Picks</span
              >
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirmation Dialog -->
    <div
      v-if="confirmationDialog.show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    >
      <div
        class="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm transform transition-all scale-100"
      >
        <h3 class="text-lg font-bold text-gray-900 mb-2">
          {{ confirmationDialog.title }}
        </h3>
        <p class="text-sm text-gray-600 mb-6">
          {{ confirmationDialog.message }}
        </p>
        <div class="flex justify-end gap-3">
          <button
            @click="confirmationDialog.show = false"
            class="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            @click="confirmationDialog.action()"
            class="px-4 py-2 text-sm font-bold text-white rounded-lg shadow-sm transition-transform active:scale-95"
            :class="
              confirmationDialog.type === 'danger'
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700'
            "
          >
            {{ confirmationDialog.confirmText || "Confirm" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Snackbar Notification -->
    <div
      v-if="snackbar.show"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-full shadow-lg flex items-center gap-3 transition-all transform"
      :class="
        snackbar.color === 'error'
          ? 'bg-red-600 text-white'
          : 'bg-slate-800 text-white'
      "
    >
      <v-img
        v-if="snackbar.icon"
        :src="snackbar.icon"
        width="20"
        height="20"
        class="invert"
      ></v-img>
      <span class="text-sm font-medium">{{ snackbar.text }}</span>
    </div>
  </div>
</template>

<script>
// KEEPING ALL ORIGINAL LOGIC INTACT AS REQUESTED
import { appAuth } from "../services/auth.js";
import OnboardingModal from "./OnboardingModal.vue";

// Import Icons
import aiAvatarIcon from "@/assets/icons/ai-avatar.svg";
import userAvatarIcon from "@/assets/icons/user-avatar.svg";
import brainIcon from "@/assets/icons/brain.svg";
import searchIcon from "@/assets/icons/search.svg";
import sendIcon from "@/assets/icons/send.svg";
import chartIcon from "@/assets/icons/chart.svg";
import sunIcon from "@/assets/icons/sun.svg";
import moonIcon from "@/assets/icons/moon.svg";
import userCircleIcon from "@/assets/icons/user-circle.svg";
import logoutIcon from "@/assets/icons/logout.svg";
import lightbulbIcon from "@/assets/icons/lightbulb.svg";
import shieldIcon from "@/assets/icons/shield.svg";
import robotIcon from "@/assets/icons/robot.svg";
import ebayIcon from "@/assets/icons/ebay.svg";
import alertIcon from "@/assets/icons/alert.svg";
import refreshIcon from "@/assets/icons/refresh.svg";
import databaseOffIcon from "@/assets/icons/database-off.svg";
import historyIcon from "@/assets/icons/history.svg";
import helpIcon from "@/assets/icons/help.svg";
import imageIcon from "@/assets/icons/image.svg";
import sparklesIcon from "@/assets/icons/sparkles.svg";
import storeIcon from "@/assets/icons/store.svg";
import truckIcon from "@/assets/icons/truck.svg";
import tagIcon from "@/assets/icons/tag.svg";
import externalLinkIcon from "@/assets/icons/external-link.svg";
import plusIcon from "@/assets/icons/plus.svg";
import arrowRightIcon from "@/assets/icons/arrow-right.svg";
import flashIcon from "@/assets/icons/flash.svg";
import shoppingIcon from "@/assets/icons/shopping.svg";
import cameraIcon from "@/assets/icons/camera.svg";

export default {
  name: "FullApp",
  components: {
    OnboardingModal,
  },
  data() {
    return {
      // Icons
      icons: {
        aiAvatar: aiAvatarIcon,
        userAvatar: userAvatarIcon,
        brain: brainIcon,
        search: searchIcon,
        send: sendIcon,
        chart: chartIcon,
        sun: sunIcon,
        moon: moonIcon,
        userCircle: userCircleIcon,
        logout: logoutIcon,
        lightbulb: lightbulbIcon,
        shield: shieldIcon,
        robot: robotIcon,
        ebay: ebayIcon,
        alert: alertIcon,
        refresh: refreshIcon,
        databaseOff: databaseOffIcon,
        history: historyIcon,
        help: helpIcon,
        image: imageIcon,
        sparkles: sparklesIcon,
        store: storeIcon,
        truck: truckIcon,
        tag: tagIcon,
        externalLink: externalLinkIcon,
        plus: plusIcon,
        arrowRight: arrowRightIcon,
        flash: flashIcon,
        shopping: shoppingIcon,
        camera: cameraIcon,
      },
      userInput: "",
      messages: [],
      // For the new layout, we track which products to show in the right panel
      activeShowcaseProducts: [],
      showMobileShowcase: false,

      resultsPageSize: 12,
      isTyping: false,
      isLoading: false,
      showWelcomeMessage: true, // Default to true initially
      isFirstMessageLoading: true,
      welcomeMessageTimestamp: "",

      // Quick suggestions
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

      // Dark mode state
      isDarkMode: false,

      // Metrics panel state
      showMetricsPanel: false, // In new layout this might be hidden or modal
      metricsData: null,
      metricsLoading: false,
      metricsError: "",
      metricsLastFetchedAt: 0,
      streamingStatus: "",
      currentQuery: "",
      metricsCacheDuration: 60000,

      // New UI State
      sortOrder: "relevance", // relevance, price_asc, price_desc
      lastQuery: "",
      isLoadingMore: false,
      hasMoreResults: true,
      currentOffset: 0,
      scrollObserver: null,

      // Dialog States
      showHelpDialog: false,
      confirmationDialog: {
        show: false,
        title: "",
        message: "",
        action: null,
      },
      snackbar: {
        show: false,
        text: "",
        color: "info",
        timeout: 4000,
        icon: null,
      },
      // Voice Interface (kept for compatibility)
      isListening: false,
      isMuted: false,
      recognition: null,
      speechSynthesis: window.speechSynthesis,
      selectedVoice: null,
    };
  },
  computed: {
    formattedMessages() {
      return this.messages;
    },
    // Keep existing computed props for compliance
    metricsStatusColor() {
      if (!this.metricsData) return "grey";
      if (!this.metricsData.metrics) return "warning";
      return this.metricsData.metrics.status === "healthy"
        ? "success"
        : "error";
    },
    metricsStatusLabel() {
      if (!this.metricsData) return "Offline";
      if (!this.metricsData.metrics) return "Syncing";
      return (
        this.metricsData.metrics.status.charAt(0).toUpperCase() +
        this.metricsData.metrics.status.slice(1)
      );
    },
    metricsLastUpdatedText() {
      if (!this.metricsLastFetchedAt) return "Never";
      const date = new Date(this.metricsLastFetchedAt);
      return date.toLocaleTimeString();
    },
    datasetMetrics() {
      return this.metricsData?.metrics?.dataset_stats || {};
    },
    feedbackMetrics() {
      return this.metricsData?.metrics?.feedback_stats || {};
    },
    userMetrics() {
      return this.metricsData?.metrics?.user_stats || {};
    },
    intentCount() {
      return this.datasetMetrics?.intent_distribution
        ? Object.keys(this.datasetMetrics.intent_distribution).length
        : 0;
    },
    topCategoryChips() {
      const categories = this.datasetMetrics?.category_distribution || {};
      if (!categories || Object.keys(categories).length === 0) return [];
      return Object.entries(categories).map(
        ([label, count]) => `${label} (${count})`
      );
    },
    topBrandChips() {
      const brands = this.datasetMetrics?.brand_distribution || {};
      if (!brands || Object.keys(brands).length === 0) return [];
      return Object.entries(brands).map(
        ([label, count]) => `${label} (${count})`
      );
    },
    sortLabel() {
      switch (this.sortOrder) {
        case "price_asc":
          return "Price Low-High";
        case "price_desc":
          return "Price High-Low";
        default:
          return "Relevance";
      }
    },
  },
  async mounted() {
    this.authCheckLoading = true;
    console.log("FullApp mounted");

    const savedDarkMode = localStorage.getItem("darkMode");
    if (savedDarkMode !== null) {
      this.isDarkMode = savedDarkMode === "true";
    }

    const authReturn = await appAuth.checkForAuthReturn();

    if (authReturn.isReturn) {
      if (authReturn.success && authReturn.authData) {
        console.log("Successfully returned from eBay auth");
        this.setAuthData(authReturn.authData);
      } else if (authReturn.error) {
        const msg = `We couldn't log you in. ${authReturn.error}`;
        this.authError = msg;
        this.showSnackbar(msg, "error", this.icons.alert);
      }
      this.authCheckLoading = false;
      this.authLoading = false;
    } else {
      const storedAuth = appAuth.getStoredAuthData();
      if (storedAuth) {
        console.log("Found stored auth data");
        this.setAuthData(storedAuth);
      } else {
        console.log("No stored auth data found");
      }
      this.authCheckLoading = false;
    }

    if (!this.loggedIn) {
      this.showWelcomeMessage = false; // Only show inside chat if logged in (in this design) or handled by template
    } else {
      setTimeout(() => {
        this.isFirstMessageLoading = false;
        this.welcomeMessageTimestamp = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      }, 1000);
    }
    this.initInfiniteScroll();
  },
  beforeUnmount() {
    this.destroyInfiniteScroll();
  },
  watch: {
    activeShowcaseProducts: {
      handler() {
        this.$nextTick(() => {
          this.setupObserver();
        });
      },
      immediate: true,
    },
  },
  methods: {
    // Infinite Scroll Implementation
    initInfiniteScroll() {
      this.scrollObserver = new IntersectionObserver(
        (entries) => {
          if (
            entries[0].isIntersecting &&
            this.hasMoreResults &&
            !this.isLoadingMore &&
            this.activeShowcaseProducts.length > 0
          ) {
            this.loadMore();
          }
        },
        { threshold: 0.1 }
      );
      this.setupObserver();
    },
    setupObserver() {
      if (!this.scrollObserver) return;
      this.$nextTick(() => {
        const target = this.$refs.scrollSentinel;
        if (target) {
          this.scrollObserver.disconnect();
          this.scrollObserver.observe(target);
        }
      });
    },
    destroyInfiniteScroll() {
      if (this.scrollObserver) {
        this.scrollObserver.disconnect();
        this.scrollObserver = null;
      }
    },
    // New Method for Split View
    setActiveShowcase(message) {
      if (message.products) {
        this.activeShowcaseProducts = message.products;
        // On mobile, switch view
        if (window.innerWidth < 768) {
          this.showMobileShowcase = true;
        }
      }
    },

    setAuthData(data) {
      this.loggedIn = true;
      this.userId = data.userId;
      this.appSessionToken = data.sessionToken || data.appSessionToken; // Handle both cases for safety
      this.ebayUsername = data.ebayUsername || data.username; // Handle naming consistency
      this.authError = "";
      this.showWelcomeMessage = true;

      this.fetchMetrics(true);
    },
    async initiateEbaySignIn() {
      this.authLoading = true;
      try {
        await appAuth.initiateEbayLogin();
      } catch (error) {
        console.error("Login initiation failed:", error);
        this.authError = "Failed to connect to eBay. Please try again.";
        this.showSnackbar(
          "Failed to connect to eBay",
          "error",
          this.icons.alert
        );
        this.authLoading = false;
      }
    },
    confirmLogout() {
      this.confirmationDialog = {
        show: true,
        title: "Sign Out",
        message: "Are you sure you want to sign out?",
        action: this.logout,
      };
    },
    logout() {
      appAuth.logout();
      this.loggedIn = false;
      this.userId = null;
      this.appSessionToken = null;
      this.ebayUsername = null;
      this.messages = [];
      this.activeShowcaseProducts = [];
      this.confirmationDialog.show = false;
      this.$emit("logout");
    },
    confirmResetChat() {
      this.confirmationDialog = {
        show: true,
        title: "Clear History",
        message: "Are you sure you want to clear the chat history?",
        action: this.resetChat,
      };
    },
    resetChat() {
      this.messages = [];
      this.activeShowcaseProducts = [];
      this.showWelcomeMessage = true;
      this.confirmationDialog.show = false;
    },
    handleConfirmation() {
      if (this.confirmationDialog.action) {
        this.confirmationDialog.action();
      }
    },
    openHelp() {
      this.showHelpDialog = true;
    },
    toggleMetricsPanel() {
      // In this layout, maybe show a modal or toggle specific view
      this.showMetricsPanel = !this.showMetricsPanel;
    },
    toggleDarkMode() {
      this.isDarkMode = !this.isDarkMode;
      localStorage.setItem("darkMode", this.isDarkMode);
    },
    handleEnterKey(e) {
      if (!e.shiftKey) {
        this.sendMessage();
      }
    },
    sendSuggestion(text) {
      this.userInput = text;
      this.sendMessage();
    },
    async sendMessage() {
      const text = this.userInput.trim();
      if (!text) return;

      this.messages.push({
        sender: "user",
        text: text,
      });

      this.userInput = "";
      this.isLoading = true;
      this.isTyping = true;
      this.lastQuery = text;
      this.currentOffset = 0;
      this.hasMoreResults = true;

      // Add placeholder AI message
      const aiMessageIndex =
        this.messages.push({
          sender: "ai",
          text: "",
          isProductResults: false, // Initially false
        }) - 1;

      // Auto-scroll
      this.$nextTick(() => {
        const chatContainer = this.$refs.chatHistoryRef;
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
      });

      try {
        const payload = {
          query: text,
          user_id: this.userId,
          session_token: this.appSessionToken,
          history: this.messages
            .filter((msg) => msg.text && msg.sender === "user")
            .slice(-3)
            .map((msg) => msg.text),
        };

        const response = await fetch("/api/nextgen/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (response.status === 401 || response.status === 403) {
          this.handleSessionExpired();
          throw new Error("Session expired");
        }

        const data = await response.json();

        // Update the placeholder message
        const aiMessage = this.messages[aiMessageIndex];
        aiMessage.text = data.response;

        if (data.items && data.items.length > 0) {
          aiMessage.isProductResults = true;
          aiMessage.products = data.items;
          aiMessage.entitiesSummary = this.buildEntitySummary(data.entities);
          // Automatically update showcase
          this.activeShowcaseProducts = data.items;
        } else {
          aiMessage.isProductResults = false; // Just text
        }
      } catch (error) {
        console.error("Chat error:", error);
        this.messages[aiMessageIndex].text =
          "I'm having trouble connecting right now. Please try again.";
        this.showSnackbar("Failed to get response", "error");
      } finally {
        this.isLoading = false;
        this.isTyping = false;
        this.$nextTick(() => {
          const chatContainer = this.$refs.chatHistoryRef;
          if (chatContainer)
            chatContainer.scrollTop = chatContainer.scrollHeight;
        });
      }
    },

    // Helper Methods
    buildEntitySummary(entities) {
      if (!entities) return [];
      return Object.entries(entities).map(([key, val]) => ({
        label: key.charAt(0).toUpperCase() + key.slice(1),
        values: Array.isArray(val) ? val : [val],
      }));
    },
    getVisibleProducts(message) {
      // Compatibility helper if template uses it
      return message.products || [];
    },
    handleSessionExpired() {
      this.showSnackbar("Session expired. Please log in again.", "warning");
      this.logout();
    },
    showSnackbar(text, color, icon) {
      this.snackbar = {
        show: true,
        text,
        color,
        timeout: 4000,
        icon,
      };
    },
    truncateText(text, length) {
      if (!text) return "";
      if (text.length <= length) return text;
      return text.substring(0, length) + "...";
    },
    formatPrice(price) {
      if (!price) return "";
      // Handle price objects or strings
      if (typeof price === "object" && price.value) {
        return `$${Number(price.value).toFixed(2)}`;
      }
      const num = Number(price);
      return isNaN(num) ? price : `$${num.toFixed(2)}`;
    },
    getPrimaryImage(product) {
      if (!product) return "";
      if (product.image && product.image.imageUrl)
        return product.image.imageUrl;
      if (product.image) return product.image;
      if (product.image_url) return product.image_url;
      if (product.galleryURL) return product.galleryURL;
      if (product.thumbnailImages && product.thumbnailImages.length) {
        return (
          product.thumbnailImages[0].imageUrl ||
          product.thumbnailImages[0].url ||
          ""
        );
      }
      return ""; // Fallback
    },
    handleImageError(product) {
      // Set fallback
      product.image = this.icons.image;
    },
    async fetchMetrics(force = false) {
      // Implementation for compatibility
      if (this.metricsLoading && !force) return;
      this.metricsLoading = true;
      try {
        const response = await fetch("/api/metrics");
        if (response.ok) {
          this.metricsData = await response.json();
          this.metricsLastFetchedAt = Date.now();
        }
      } catch (e) {
        console.error(e);
      } finally {
        this.metricsLoading = false;
      }
    },
    toggleSort() {
      if (this.sortOrder === "relevance") this.sortOrder = "price_asc";
      else if (this.sortOrder === "price_asc") this.sortOrder = "price_desc";
      else this.sortOrder = "relevance";

      this.sortProducts();
    },
    sortProducts() {
      if (
        !this.activeShowcaseProducts ||
        this.activeShowcaseProducts.length === 0
      )
        return;

      if (this.sortOrder === "relevance") {
        this.activeShowcaseProducts.sort(
          (a, b) => (b.score || 0) - (a.score || 0)
        );
      } else if (this.sortOrder === "price_asc") {
        this.activeShowcaseProducts.sort((a, b) => {
          const pA = this.parsePrice(a.price);
          const pB = this.parsePrice(b.price);
          return pA - pB;
        });
      } else if (this.sortOrder === "price_desc") {
        this.activeShowcaseProducts.sort((a, b) => {
          const pA = this.parsePrice(a.price);
          const pB = this.parsePrice(b.price);
          return pB - pA;
        });
      }
    },
    parsePrice(priceObj) {
      if (!priceObj) return 0;
      if (typeof priceObj === "number") return priceObj;
      if (priceObj.value) return parseFloat(priceObj.value);
      if (typeof priceObj === "string")
        return parseFloat(priceObj.replace(/[^0-9.]/g, ""));
      return 0;
    },
    async loadMore() {
      if (this.isLoadingMore || !this.lastQuery) return;
      this.isLoadingMore = true;

      // Use the actual number of items we have as the offset to avoid overlaps
      const fetchOffset = this.activeShowcaseProducts.length;

      try {
        const payload = {
          query: this.lastQuery,
          user_id: this.userId,
          session_token: this.appSessionToken,
          offset: fetchOffset,
          limit: this.resultsPageSize,
        };

        const response = await fetch("/api/nextgen/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (data.items && data.items.length > 0) {
          // Append and deduplicate
          const existingIds = new Set(
            this.activeShowcaseProducts.map((p) => p.item_id)
          );
          const newUniqueItems = data.items.filter(
            (p) => !existingIds.has(p.item_id)
          );

          if (newUniqueItems.length > 0) {
            this.activeShowcaseProducts = [
              ...this.activeShowcaseProducts,
              ...newUniqueItems,
            ];
            // Apply current sort
            this.sortProducts();
          } else if (data.items.length > 0) {
            // If we got items but they were all duplicates, try to fetch from further deep by jumping the offset
            this.currentOffset += 20;
            this.loadMore();
          }
        } else {
          this.hasMoreResults = false;
        }
      } catch (e) {
        console.error("Load more error:", e);
        this.showSnackbar("Could not load more results", "error");
      } finally {
        this.isLoadingMore = false;
      }
    },
  },
};
</script>

<style scoped>
/* Tailwind handles almost everything, but adding some custom utility behaviors */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #e5e7eb;
  border-radius: 20px;
}
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Animations */
@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-25%);
  }
}
.animate-bounce {
  animation: bounce 1s infinite;
}
.delay-100 {
  animation-delay: 100ms;
}
.delay-200 {
  animation-delay: 200ms;
}
</style>
