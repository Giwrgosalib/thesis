<!-- filepath: frontend/src/components/FullApp.vue -->
<template>
  <v-app class="ebay-chat-app" :class="{ 'dark-mode': isDarkMode }">
    <!-- Enhanced Header with AI Showcase -->
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
            <p class="app-subtitle">
              Advanced NLP • Enhanced NER • Smart Search
            </p>
          </div>
        </div>

        <div class="header-actions">
          <!-- AI Status Indicator -->
          <v-chip
            v-if="loggedIn"
            color="success"
            variant="flat"
            class="ai-status-chip"
          >
            <v-icon start>mdi-brain</v-icon>
            AI Active
          </v-chip>

          <!-- System Metrics Toggle -->
          <v-btn
            v-if="loggedIn"
            @click="toggleMetricsPanel"
            variant="text"
            color="ebay-blue"
            class="metrics-toggle"
            size="small"
          >
            <v-icon>mdi-chart-line</v-icon>
          </v-btn>

          <!-- Dark Mode Toggle -->
          <v-btn
            @click="toggleDarkMode"
            variant="text"
            color="ebay-blue"
            class="theme-toggle"
            size="small"
          >
            <v-icon>{{
              isDarkMode ? "mdi-weather-sunny" : "mdi-weather-night"
            }}</v-icon>
          </v-btn>

          <!-- User Info -->
          <v-chip
            v-if="loggedIn"
            color="success"
            variant="flat"
            class="user-chip"
          >
            <v-icon start>mdi-account-circle</v-icon>
            {{ ebayUsername }}
          </v-chip>

          <!-- Logout -->
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
        <!-- Enhanced Login View with AI Showcase -->
        <v-row
          v-if="!loggedIn"
          justify="center"
          align="center"
          class="fill-height login-container"
        >
          <v-col cols="12" md="8" lg="6" xl="5">
            <v-card class="login-card" elevation="8">
              <div class="login-header">
                <div class="login-icon">
                  <v-icon size="80" color="ebay-red">mdi-robot</v-icon>
                </div>
                <h2 class="login-title">eBay AI Shopping Assistant</h2>
                <p class="login-subtitle">
                  Advanced AI-powered product discovery with enhanced NLP
                </p>
              </div>

              <v-card-text class="login-content">
                <!-- AI Capabilities Showcase -->
                <div class="ai-capabilities">
                  <h3 class="capabilities-title">
                    🤖 AI Agents & Capabilities
                  </h3>
                  <div class="capabilities-grid">
                    <div class="capability-card">
                      <v-icon color="ebay-blue" size="32">mdi-brain</v-icon>
                      <h4>Enhanced NLP</h4>
                      <p>BiLSTM-CRF with 208 entity types</p>
                    </div>
                    <div class="capability-card">
                      <v-icon color="ebay-green" size="32">mdi-magnify</v-icon>
                      <h4>Smart Search</h4>
                      <p>Intelligent product matching</p>
                    </div>
                    <div class="capability-card">
                      <v-icon color="ebay-yellow" size="32"
                        >mdi-lightbulb</v-icon
                      >
                      <h4>Learning System</h4>
                      <p>Adaptive user preferences</p>
                    </div>
                    <div class="capability-card">
                      <v-icon color="ebay-red" size="32"
                        >mdi-shield-check</v-icon
                      >
                      <h4>Secure OAuth</h4>
                      <p>eBay API integration</p>
                    </div>
                  </div>
                </div>

                <!-- Technical Features -->
                <div class="features-list">
                  <div class="feature-item">
                    <v-icon color="ebay-blue" class="feature-icon"
                      >mdi-robot</v-icon
                    >
                    <span>Single Intent Architecture (100% accuracy)</span>
                  </div>
                  <div class="feature-item">
                    <v-icon color="ebay-yellow" class="feature-icon"
                      >mdi-brain</v-icon
                    >
                    <span>1.75M parameter BiLSTM-CRF model</span>
                  </div>
                  <div class="feature-item">
                    <v-icon color="ebay-green" class="feature-icon"
                      >mdi-chart-line</v-icon
                    >
                    <span>Real-time analytics & metrics</span>
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

        <!-- Enhanced Chat Interface with Metrics Panel -->
        <v-row v-else class="fill-height chat-container">
          <!-- Metrics Panel (Sidebar) -->
          <v-col
            v-if="showMetricsPanel"
            cols="12"
            md="4"
            lg="3"
            class="metrics-panel"
          >
            <v-card class="metrics-card" elevation="2">
              <v-card-title class="metrics-header">
                <v-icon color="ebay-blue" class="mr-2">mdi-chart-line</v-icon>
                System Metrics
                <v-spacer></v-spacer>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  :disabled="metricsLoading"
                  @click="fetchMetrics(true)"
                >
                  <v-icon size="18">mdi-refresh</v-icon>
                </v-btn>
              </v-card-title>
              <v-card-text class="metrics-content">
                <div v-if="metricsLoading" class="metrics-loading">
                  <v-progress-circular
                    indeterminate
                    color="ebay-blue"
                  ></v-progress-circular>
                  <span>Syncing analytics...</span>
                </div>
                <v-alert
                  v-else-if="metricsError"
                  type="error"
                  density="comfortable"
                  variant="tonal"
                >
                  <v-icon start>mdi-alert</v-icon>
                  {{ metricsError }}
                </v-alert>
                <template v-else-if="metricsData">
                  <div class="metric-item">
                    <div class="metric-label">AI Status</div>
                    <v-chip :color="metricsStatusColor" size="small">
                      {{ metricsStatusLabel }}
                    </v-chip>
                  </div>
                  <div class="metric-item" v-if="feedbackMetrics">
                    <div class="metric-label">Feedback Quality</div>
                    <div class="metric-value">
                      {{ feedbackMetrics.total_feedback || 0 }} entries · Avg
                      score
                      {{
                        feedbackMetrics.average_rating !== undefined
                          ? feedbackMetrics.average_rating
                          : "N/A"
                      }}
                    </div>
                  </div>
                  <div class="metric-item" v-if="userMetrics">
                    <div class="metric-label">Active Preference Profiles</div>
                    <div class="metric-value">
                      {{ userMetrics.total_users || 0 }} users · Sample
                      {{ userMetrics.sample_size || 0 }}
                    </div>
                  </div>
                  <div class="metric-item" v-if="datasetMetrics">
                    <div class="metric-label">Training Dataset</div>
                    <div class="metric-value">
                      {{
                        datasetMetrics.metrics?.dataset_name ||
                        "Enhanced BiLSTM-CRF"
                      }}
                      ·
                      {{
                        datasetMetrics.total_samples !== undefined
                          ? datasetMetrics.total_samples
                          : "N/A"
                      }}
                      samples
                    </div>
                  </div>
                  <div
                    class="metric-item"
                    v-if="feedbackMetrics?.positive_feedback_percentage"
                  >
                    <div class="metric-label">Positive Feedback</div>
                    <div class="metric-value">
                      {{ feedbackMetrics.positive_feedback_percentage }}%
                      positive
                    </div>
                  </div>
                  <div class="metric-item" v-if="intentCount">
                    <div class="metric-label">Intent Coverage</div>
                    <div class="metric-value">
                      {{ intentCount }} tracked intents
                    </div>
                  </div>
                  <div
                    class="metric-item"
                    v-if="topCategoryChips.length || topBrandChips.length"
                  >
                    <div class="metric-label">Trending Entities</div>
                    <div class="entity-chips compact">
                      <template
                        v-for="(chip, idx) in topCategoryChips"
                        :key="'cat-' + idx"
                      >
                        <v-chip color="ebay-blue" size="x-small" label>
                          {{ chip }}
                        </v-chip>
                      </template>
                      <template
                        v-for="(chip, idx) in topBrandChips"
                        :key="'brand-' + idx"
                      >
                        <v-chip color="ebay-green" size="x-small" label>
                          {{ chip }}
                        </v-chip>
                      </template>
                    </div>
                  </div>
                  <div class="metric-item">
                    <div class="metric-label">Queries This Session</div>
                    <div class="metric-value">{{ messages.length }}</div>
                  </div>
                  <small class="metrics-timestamp">
                    Last synced: {{ metricsLastUpdatedText }}
                  </small>
                </template>
                <div v-else class="metrics-empty">
                  <v-icon color="grey">mdi-database-off</v-icon>
                  <p>Analytics data will appear once synced.</p>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- Main Chat Area -->
          <v-col
            :cols="showMetricsPanel ? 12 : 12"
            :md="showMetricsPanel ? 8 : 12"
            :lg="showMetricsPanel ? 9 : 12"
            class="d-flex flex-column"
          >
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
                        <div class="ai-intro">
                          <div class="ai-badge">
                            <v-icon color="ebay-red" class="mr-2"
                              >mdi-robot</v-icon
                            >
                            <span>Enhanced AI Assistant</span>
                          </div>
                          <p class="welcome-text">
                            Hello! I'm your advanced eBay AI shopping assistant
                            powered by
                            <strong>BiLSTM-CRF neural networks</strong> with
                            <strong>208 entity types</strong> and
                            <strong>1.75M parameters</strong>. I can understand
                            complex product queries and provide intelligent
                            recommendations.
                          </p>
                        </div>

                        <div class="ai-capabilities-showcase">
                          <h4>🧠 AI Capabilities</h4>
                          <div class="capability-tags">
                            <v-chip
                              color="ebay-blue"
                              size="small"
                              variant="flat"
                              >Single Intent (100%)</v-chip
                            >
                            <v-chip
                              color="ebay-green"
                              size="small"
                              variant="flat"
                              >Enhanced NER</v-chip
                            >
                            <v-chip
                              color="ebay-yellow"
                              size="small"
                              variant="flat"
                              >Smart Search</v-chip
                            >
                            <v-chip color="ebay-red" size="small" variant="flat"
                              >Learning System</v-chip
                            >
                          </div>
                        </div>

                        <div class="suggestion-chips">
                          <h4>💡 Try these examples:</h4>
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
                          <div class="results-header">
                            <v-icon color="ebay-blue" class="results-icon"
                              >mdi-lightning-bolt</v-icon
                            >
                            <div class="results-text">
                              <h4>Curated matches for your search</h4>
                              <p>
                                {{
                                  message.text ||
                                  "These listings balance price, condition, and seller reputation."
                                }}
                              </p>
                            </div>
                          </div>
                          <div
                            v-if="
                              message.entitiesSummary &&
                              message.entitiesSummary.length
                            "
                            class="entity-summary"
                          >
                            <span class="entity-summary-label"
                              >Understood details:</span
                            >
                            <div class="entity-chips">
                              <v-chip
                                v-for="(
                                  entity, eIndex
                                ) in message.entitiesSummary"
                                :key="eIndex"
                                class="entity-chip"
                                color="ebay-blue"
                                text-color="white"
                                label
                              >
                                {{ entity.label }}:
                                {{ entity.values.join(", ") }}
                              </v-chip>
                            </div>
                          </div>
                          <div class="products-grid">
                            <v-card
                              v-for="(product, idx) in getVisibleProducts(
                                message
                              )"
                              :key="idx"
                              class="product-card"
                              elevation="3"
                            >
                              <div class="product-image-container">
                                <v-img
                                  v-if="getPrimaryImage(product)"
                                  :src="getPrimaryImage(product)"
                                  height="190"
                                  cover
                                  class="product-image"
                                >
                                  <template v-slot:placeholder>
                                    <div class="image-placeholder">
                                      <v-icon size="42" color="grey-lighten-2"
                                        >mdi-image</v-icon
                                      >
                                    </div>
                                  </template>
                                </v-img>
                                <div v-else class="image-placeholder">
                                  <v-icon size="42" color="grey-lighten-2"
                                    >mdi-image</v-icon
                                  >
                                </div>
                              </div>
                              <div class="product-content">
                                <h3
                                  class="product-title"
                                  :title="product.title"
                                >
                                  {{ truncateText(product.title, 80) }}
                                </h3>
                                <div class="product-meta">
                                  <span class="product-price">{{
                                    formatPrice(product.price)
                                  }}</span>
                                  <v-chip
                                    v-if="product.condition"
                                    :color="
                                      getConditionColor(product.condition)
                                    "
                                    size="small"
                                    variant="flat"
                                    class="condition-chip"
                                  >
                                    {{ product.condition }}
                                  </v-chip>
                                </div>
                                <div class="product-attributes">
                                  <div
                                    class="product-attribute"
                                    v-if="getSellerSummary(product)"
                                  >
                                    <v-icon>mdi-storefront-outline</v-icon>
                                    <span>{{ getSellerSummary(product) }}</span>
                                  </div>
                                  <div
                                    class="product-attribute"
                                    v-if="getShippingSummary(product)"
                                  >
                                    <v-icon>mdi-truck-delivery-outline</v-icon>
                                    <span>{{
                                      getShippingSummary(product)
                                    }}</span>
                                  </div>
                                  <div
                                    class="product-attribute"
                                    v-if="getPrimaryCategories(product).length"
                                  >
                                    <v-icon>mdi-tag-multiple-outline</v-icon>
                                    <span>{{
                                      getPrimaryCategories(product).join(", ")
                                    }}</span>
                                  </div>
                                </div>
                              </div>
                              <v-divider class="product-divider"></v-divider>
                              <v-card-actions class="product-actions">
                                <div class="product-actions-left">
                                  <v-chip
                                    v-if="product.priorityListing"
                                    color="ebay-yellow"
                                    variant="flat"
                                    size="small"
                                  >
                                    Promoted
                                  </v-chip>
                                  <v-chip
                                    v-if="product.topRatedBuyingExperience"
                                    color="success"
                                    size="small"
                                    variant="flat"
                                  >
                                    Top rated
                                  </v-chip>
                                </div>
                                <v-btn
                                  :href="
                                    product.itemWebUrl || product.publicUrl
                                  "
                                  target="_blank"
                                  color="ebay-blue"
                                  variant="flat"
                                  size="small"
                                  class="view-btn"
                                >
                                  <v-icon>mdi-open-in-new</v-icon>
                                  View
                                </v-btn>
                              </v-card-actions>
                            </v-card>
                          </div>

                          <!-- Show More Button -->
                          <div
                            v-if="
                              hasMoreResults && message.products.length >= 10
                            "
                            class="show-more-container"
                          >
                            <v-btn
                              variant="outlined"
                              color="ebay-blue"
                              :loading="isLoadingMore"
                              @click="loadMore(index)"
                              prepend-icon="mdi-plus"
                            >
                              Show More Results
                            </v-btn>
                          </div>

                          <!-- Streaming Status -->
                          <div
                            v-if="message.streaming && streamingStatus"
                            class="streaming-status"
                          >
                            <v-progress-circular
                              indeterminate
                              size="16"
                              width="2"
                              color="ebay-blue"
                              class="mr-2"
                            ></v-progress-circular>
                            <span>{{ streamingStatus }}</span>
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
      resultsPageSize: 4,
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

      // Dark mode state
      isDarkMode: false,

      // Metrics panel state
      showMetricsPanel: false,
      metricsData: null,
      metricsLoading: false,
      metricsError: "",
      metricsLastFetchedAt: 0,
      streamingStatus: "",
      currentOffset: 0,
      hasMoreResults: true,
      isLoadingMore: false,
      currentQuery: "",
      metricsCacheDuration: 60000,
    };
  },

  async mounted() {
    this.authCheckLoading = true;
    console.log("FullApp mounted");

    // Load dark mode preference
    const savedDarkMode = localStorage.getItem("darkMode");
    if (savedDarkMode !== null) {
      this.isDarkMode = savedDarkMode === "true";
    }

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

  computed: {
    feedbackMetrics() {
      return this.metricsData?.feedback_metrics || null;
    },
    userMetrics() {
      return this.metricsData?.user_metrics || null;
    },
    datasetMetrics() {
      return this.metricsData?.dataset_metrics || null;
    },
    metricsStatusLabel() {
      const status =
        this.feedbackMetrics?.status ||
        this.datasetMetrics?.status ||
        "unknown";
      if (status === "success") {
        return "Operational";
      }
      if (status === "error") {
        return "Degraded";
      }
      if (status === "empty" || status === "no_data") {
        return "Limited Data";
      }
      return status ? status.replace(/_/g, " ").toUpperCase() : "Unknown";
    },
    metricsStatusColor() {
      const status =
        this.feedbackMetrics?.status ||
        this.datasetMetrics?.status ||
        "unknown";
      if (status === "success") {
        return "success";
      }
      if (status === "error") {
        return "error";
      }
      if (status === "empty" || status === "no_data") {
        return "warning";
      }
      return "primary";
    },
    topCategoryChips() {
      const categories = this.userMetrics?.top_categories;
      if (!categories) {
        return [];
      }
      return Object.entries(categories).map(
        ([label, count]) => `${label} (${count})`
      );
    },
    topBrandChips() {
      const brands = this.userMetrics?.top_brands;
      if (!brands) {
        return [];
      }
      return Object.entries(brands).map(
        ([label, count]) => `${label} (${count})`
      );
    },
    intentCount() {
      const intents = this.datasetMetrics?.metrics?.intent_distribution;
      if (!intents) {
        return 0;
      }
      return Object.keys(intents).length;
    },
    metricsLastUpdatedText() {
      if (!this.metricsLastFetchedAt) {
        return "waiting for sync";
      }
      try {
        return new Date(this.metricsLastFetchedAt).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      } catch (error) {
        return "recently";
      }
    },
  },

  watch: {
    showMetricsPanel(newValue) {
      if (newValue) {
        this.fetchMetrics();
      }
    },
    loggedIn(newValue) {
      if (newValue) {
        if (this.showMetricsPanel) {
          this.fetchMetrics(true);
        }
      } else {
        this.metricsData = null;
        this.metricsLastFetchedAt = 0;
      }
    },
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
      this.metricsData = null;
      this.metricsLastFetchedAt = 0;

      console.log("User logged out");
    },

    handleSessionExpired(
      message = "Your session has expired. Please sign in again."
    ) {
      console.warn("Session expired:", message);
      appAuth.clearStoredAuthData();
      this.loggedIn = false;
      this.userId = null;
      this.appSessionToken = null;
      this.ebayUsername = null;
      this.messages = [];
      this.showWelcomeMessage = false;
      this.authError = message;
      this.metricsData = null;
      this.metricsLastFetchedAt = 0;
    },

    async fetchMetrics(force = false) {
      if (!this.loggedIn) {
        return;
      }
      if (this.metricsLoading) {
        return;
      }
      const now = Date.now();
      if (
        !force &&
        this.metricsData &&
        now - this.metricsLastFetchedAt < this.metricsCacheDuration
      ) {
        return;
      }

      this.metricsLoading = true;
      this.metricsError = "";

      try {
        const headers = {
          Accept: "application/json",
        };
        if (this.appSessionToken) {
          headers["Authorization"] = `Bearer ${this.appSessionToken}`;
        }

        const response = await fetch("/api/nextgen/metrics", {
          method: "GET",
          headers,
        });

        if (response.status === 401 || response.status === 403) {
          this.handleSessionExpired(
            "Session expired while loading analytics. Please sign in again."
          );
          throw new Error("Authentication required");
        }

        const text = await response.text();
        let payload = null;
        if (text) {
          try {
            payload = JSON.parse(text);
          } catch (parseError) {
            console.error("Failed to parse metrics payload", parseError);
          }
        }

        if (!response.ok) {
          throw new Error(
            (payload && (payload.error || payload.message)) ||
              `Metrics request failed: ${response.status}`
          );
        }

        this.metricsData = payload || {};
        this.metricsLastFetchedAt = Date.now();
      } catch (error) {
        console.error("Failed to fetch metrics:", error);
        this.metricsError =
          error?.message || "Unable to load metrics at this time.";
      } finally {
        this.metricsLoading = false;
      }
    },

    async sendMessage() {
      if (this.userInput.trim() === "") return;

      // Reset pagination state for new query
      this.currentQuery = this.userInput;
      this.currentOffset = 0;
      this.hasMoreResults = true;

      this.messages.push({
        sender: "user",
        text: this.userInput,
        timestamp: this.getCurrentTimestamp(),
      });

      this.userInput = "";
      this.isTyping = true;
      this.isLoading = true;
      this.streamingStatus = "Starting...";

      // Create a placeholder message for the AI response
      const aiMessage = {
        sender: "ai",
        text: "",
        products: [],
        isProductResults: false,
        timestamp: this.getCurrentTimestamp(),
        streaming: true,
      };
      this.messages.push(aiMessage);

      await this.fetchStream(this.currentQuery, 0, aiMessage);
    },

    async loadMore(messageIndex) {
      const message = this.messages[messageIndex];
      if (!message) return;

      this.currentOffset += 10;
      this.isLoadingMore = true;

      await this.fetchStream(
        this.currentQuery,
        this.currentOffset,
        message,
        true
      );

      this.isLoadingMore = false;
    },

    async fetchStream(query, offset, messageObject, isLoadMore = false) {
      try {
        const requestBody = {
          query: query,
          user_context: this.buildUserContext(),
          limit: 10,
          offset: offset,
        };

        const headers = {
          "Content-Type": "application/json",
        };

        if (this.loggedIn && this.appSessionToken) {
          headers["Authorization"] = `Bearer ${this.appSessionToken}`;
        }

        const response = await fetch(`/api/nextgen/query`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        let isReading = true;
        while (isReading) {
          const { done, value } = await reader.read();
          if (done) {
            isReading = false;
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const jsonStr = line.slice(6);
              try {
                const event = JSON.parse(jsonStr);
                this.handleStreamEvent(event, messageObject, isLoadMore);
              } catch (e) {
                console.error("Error parsing stream event", e);
              }
            }
          }
        }
      } catch (error) {
        console.error("Stream error:", error);
        messageObject.text += `\n[Error: ${error.message}]`;
      } finally {
        this.isTyping = false;
        this.isLoading = false;
        this.streamingStatus = "";
        messageObject.streaming = false;
      }
    },

    handleStreamEvent(event, message, isLoadMore) {
      if (event.type === "status") {
        this.streamingStatus = event.content;
      } else if (event.type === "results") {
        const newProducts = event.content.items || [];
        if (newProducts.length < 10) {
          this.hasMoreResults = false;
        }

        if (isLoadMore) {
          message.products.push(...newProducts);
        } else {
          message.products = newProducts;
          message.isProductResults = newProducts.length > 0;
          message.entitiesSummary = this.buildEntitySummary(
            event.content.entities
          );
          message.citations = event.content.citations;
        }
      } else if (event.type === "token") {
        message.text += event.content;
      } else if (event.type === "done") {
        // Stream finished
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
    getPrimaryImage(product) {
      if (!product) {
        return null;
      }
      const sources = [
        product.image?.imageUrl,
        product.thumbnailImages?.[0]?.imageUrl,
        product.additionalImages?.[0]?.imageUrl,
      ];
      return sources.find((src) => src) || null;
    },

    formatPrice(price) {
      const formatted = this.formatMoney(price);
      return formatted || "Price unavailable";
    },

    formatMoney(price) {
      if (!price || price.value == null) {
        return null;
      }
      const currency = price.currency || "USD";
      const numeric = Number(price.value);
      if (!Number.isFinite(numeric)) {
        return price.value ? `${currency} ${price.value}` : null;
      }
      try {
        return new Intl.NumberFormat(undefined, {
          style: "currency",
          currency,
          maximumFractionDigits: numeric % 1 === 0 ? 0 : 2,
        }).format(numeric);
      } catch (error) {
        return `${currency} ${numeric.toFixed(2)}`;
      }
    },

    getSellerSummary(product) {
      const seller = product?.seller;
      if (!seller) {
        return "";
      }
      const summaryParts = [];
      if (seller.username) {
        summaryParts.push(seller.username);
      }
      if (seller.feedbackScore) {
        summaryParts.push(
          `${Number(seller.feedbackScore).toLocaleString()} feedback`
        );
      }
      if (seller.feedbackPercentage) {
        summaryParts.push(`${seller.feedbackPercentage}% positive`);
      }
      return summaryParts.join(" | ");
    },

    getShippingSummary(product) {
      const option = product?.shippingOptions?.[0];
      if (!option) {
        return "";
      }
      const value = option.shippingCost?.value;
      let costText = "";
      if (value === "0" || value === "0.0" || value === "0.00") {
        costText = "Free shipping";
      } else {
        const formatted = this.formatMoney(option.shippingCost);
        if (formatted) {
          costText = `Shipping ${formatted}`;
        }
      }
      const deliveryWindow = this.formatDeliveryWindow(option);
      return [costText, deliveryWindow].filter(Boolean).join(" | ");
    },

    formatDeliveryWindow(option) {
      if (!option) {
        return "";
      }
      const formatDate = (raw) => {
        if (!raw) {
          return null;
        }
        const parsed = new Date(raw);
        if (Number.isNaN(parsed.getTime())) {
          return null;
        }
        return parsed.toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        });
      };
      const from = formatDate(option.minEstimatedDeliveryDate);
      const to = formatDate(option.maxEstimatedDeliveryDate);
      if (from && to && from !== to) {
        return `${from} - ${to}`;
      }
      return to || from || "";
    },

    getPrimaryCategories(product) {
      const categories = product?.categories;
      if (!Array.isArray(categories)) {
        return [];
      }
      return categories
        .filter((category) => category?.categoryName)
        .slice(0, 2)
        .map((category) => category.categoryName);
    },

    truncateText(text, limit = 80) {
      if (typeof text !== "string") {
        return "";
      }
      if (text.length <= limit) {
        return text;
      }
      return `${text.slice(0, limit).trim()}...`;
    },

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

    buildUserContext() {
      return {
        userId: this.userId || null,
        ebayUsername: this.ebayUsername || null,
        loggedIn: this.loggedIn,
      };
    },

    buildEntitySummary(entityPayload) {
      if (!entityPayload || typeof entityPayload !== "object") {
        return [];
      }
      const buckets = entityPayload.entities || {};
      return Object.entries(buckets)
        .filter(([, values]) => Array.isArray(values) && values.length > 0)
        .map(([label, values]) => ({
          label,
          values: values.map((value) => String(value)),
        }));
    },

    getVisibleProducts(message) {
      const products = Array.isArray(message?.products) ? message.products : [];
      const limit = message?.visibleCount ?? this.resultsPageSize;
      return products.slice(0, limit);
    },

    hasMoreProducts(message) {
      return (
        Array.isArray(message?.products) &&
        (message.visibleCount ?? this.resultsPageSize) < message.products.length
      );
    },

    showMoreProducts(index) {
      const message = this.messages[index];
      if (!message || !Array.isArray(message.products)) {
        return;
      }
      const current = message.visibleCount ?? this.resultsPageSize;
      const nextCount = Math.min(
        current + this.resultsPageSize,
        message.products.length
      );
      if (typeof this.$set === "function") {
        this.$set(this.messages[index], "visibleCount", nextCount);
      } else {
        this.messages[index].visibleCount = nextCount;
      }
    },

    // Dark mode toggle
    toggleDarkMode() {
      this.isDarkMode = !this.isDarkMode;
      localStorage.setItem("darkMode", this.isDarkMode);
    },

    // Metrics panel toggle
    toggleMetricsPanel() {
      this.showMetricsPanel = !this.showMetricsPanel;
    },
  },
};
</script>

<style scoped>
.show-more-container {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  margin-bottom: 8px;
}

.streaming-status {
  display: flex;
  align-items: center;
  margin-top: 12px;
  font-size: 0.9rem;
  color: #666;
  font-style: italic;
}
</style>
