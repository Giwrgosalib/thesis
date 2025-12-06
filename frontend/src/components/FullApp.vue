<!-- filepath: frontend/src/components/FullApp.vue -->
<template>
  <v-app class="ebay-chat-app" :class="{ 'dark-mode': isDarkMode }">
    <OnboardingModal v-if="userId" :userId="userId" />
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
            <v-img
              :src="icons.brain"
              width="20"
              height="20"
              class="mr-2"
            ></v-img>
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
            <v-img :src="icons.chart" width="24" height="24"></v-img>
          </v-btn>

          <!-- Dark Mode Toggle -->
          <v-btn
            @click="toggleDarkMode"
            variant="text"
            color="ebay-blue"
            class="theme-toggle"
            size="small"
          >
            <v-img
              :src="isDarkMode ? icons.sun : icons.moon"
              width="24"
              height="24"
            ></v-img>
          </v-btn>

          <!-- Reset Chat -->
          <v-btn
            v-if="loggedIn"
            @click="confirmResetChat"
            variant="text"
            color="ebay-blue"
            class="reset-chat-btn"
            size="small"
            title="Reset Chat"
          >
            <v-img :src="icons.refresh" width="24" height="24"></v-img>
          </v-btn>

          <!-- Help Button -->
          <v-btn
            @click="openHelp"
            variant="text"
            color="ebay-blue"
            class="help-btn"
            size="small"
            title="Help"
          >
            <v-img :src="icons.help" width="24" height="24"></v-img>
          </v-btn>

          <!-- User Info -->
          <v-chip
            v-if="loggedIn"
            color="success"
            variant="flat"
            class="user-chip"
          >
            <v-img
              :src="icons.userCircle"
              width="20"
              height="20"
              class="mr-2"
            ></v-img>
            {{ ebayUsername }}
          </v-chip>

          <!-- Logout -->
          <v-btn
            v-if="loggedIn"
            @click="confirmLogout"
            variant="outlined"
            color="ebay-red"
            class="logout-btn"
          >
            <v-img
              :src="icons.logout"
              width="20"
              height="20"
              class="mr-2"
            ></v-img>
            Logout
          </v-btn>
        </div>
      </div>
    </v-app-bar>

    <!-- Help Dialog -->
    <v-dialog v-model="showHelpDialog" max-width="600">
      <v-card>
        <v-card-title class="headline">
          <v-icon color="ebay-blue" class="mr-2">mdi-help-circle</v-icon>
          How to use eBay AI Assistant
        </v-card-title>
        <v-card-text>
          <p class="mb-3">
            Welcome to the advanced eBay AI Shopping Assistant! Here's how you
            can get the most out of it:
          </p>
          <v-list density="compact">
            <v-list-item prepend-icon="mdi-magnify" title="Search for Products">
              <v-list-item-subtitle>
                Ask for products naturally, e.g., "Find me a vintage Gibson Les
                Paul under $3000".
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item prepend-icon="mdi-brain" title="AI Capabilities">
              <v-list-item-subtitle>
                The "AI Active" indicator means our advanced NLP model is
                processing your queries to understand context and entities.
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item prepend-icon="mdi-chart-bar" title="System Metrics">
              <v-list-item-subtitle>
                Toggle the metrics panel to see real-time performance data of
                the AI model.
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="ebay-blue"
            variant="text"
            @click="showHelpDialog = false"
            >Got it</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirmation Dialog -->
    <v-dialog v-model="confirmationDialog.show" max-width="400">
      <v-card>
        <v-card-title class="headline">{{
          confirmationDialog.title
        }}</v-card-title>
        <v-card-text>{{ confirmationDialog.message }}</v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="grey-darken-1"
            variant="text"
            @click="confirmationDialog.show = false"
            >Cancel</v-btn
          >
          <v-btn color="ebay-red" variant="text" @click="handleConfirmation"
            >Confirm</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Global System Notification Snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="snackbar.timeout"
      location="top"
      elevation="4"
    >
      <div class="d-flex align-center">
        <v-icon
          v-if="snackbar.icon"
          :icon="snackbar.icon"
          class="mr-2"
          size="small"
        ></v-icon>
        {{ snackbar.text }}
      </div>
      <template v-slot:actions>
        <v-btn
          variant="text"
          @click="snackbar.show = false"
          icon="mdi-close"
          size="small"
        ></v-btn>
      </template>
    </v-snackbar>

    <v-main>
      <v-container fluid class="fill-height" style="min-height: 100vh">
        <!-- Modern Hero Landing Section -->
        <div v-if="!loggedIn" class="hero-section">
          <div class="hero-content-left">
            <div class="hero-badge">
              <v-img
                :src="icons.sparkles"
                width="16"
                height="16"
                class="mr-2"
              ></v-img>
              <span>Next-Gen AI Shopping</span>
            </div>
            <h1 class="hero-title">
              Discover Products <br />
              <span class="text-gradient">Intelligently</span>
            </h1>
            <p class="hero-subtitle">
              Experience the future of eBay shopping with our advanced AI
              assistant. Powered by BiLSTM-CRF neural networks for precise
              understanding.
            </p>

            <div class="hero-actions">
              <v-btn
                @click="initiateEbaySignIn"
                color="ebay-blue"
                size="x-large"
                class="hero-btn glow-button"
                :loading="authLoading"
                :disabled="authLoading"
                elevation="8"
              >
                <v-img
                  :src="icons.ebay"
                  width="28"
                  height="28"
                  class="mr-3 bg-white rounded-circle pa-1"
                ></v-img>
                {{ authLoading ? "Connecting..." : "Sign in with eBay" }}
                <v-img
                  :src="icons.arrowRight"
                  width="24"
                  height="24"
                  class="ml-3"
                ></v-img>
              </v-btn>

              <div v-if="authError" class="hero-error mt-4">
                <v-img
                  :src="icons.alert"
                  width="20"
                  height="20"
                  class="mr-2"
                ></v-img>
                {{ authError }}
              </div>
            </div>

            <div class="hero-stats">
              <div class="stat-item">
                <span class="stat-value">1.75M</span>
                <span class="stat-label">Parameters</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-value">208</span>
                <span class="stat-label">Entity Types</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-value">100%</span>
                <span class="stat-label">Intent Accuracy</span>
              </div>
            </div>
          </div>

          <div class="hero-content-right">
            <div class="glass-stack floating-animation">
              <!-- Back Card (Decorative) -->
              <div class="glass-card back-card"></div>

              <!-- Main Showcase Card -->
              <div class="glass-card main-card">
                <div class="card-header">
                  <div class="header-dots">
                    <span class="dot red"></span>
                    <span class="dot yellow"></span>
                    <span class="dot green"></span>
                  </div>
                  <div class="header-badge">AI Active</div>
                </div>

                <div class="showcase-content">
                  <div class="ai-message-preview">
                    <v-avatar size="40" color="ebay-red" class="mb-3">
                      <v-img :src="icons.aiAvatar"></v-img>
                    </v-avatar>
                    <div class="typing-lines">
                      <div class="line long"></div>
                      <div class="line medium"></div>
                      <div class="line short"></div>
                    </div>
                  </div>

                  <div class="feature-grid">
                    <div class="feature-box">
                      <v-img
                        :src="icons.brain"
                        width="32"
                        height="32"
                        class="mb-2"
                      ></v-img>
                      <span>NLP</span>
                    </div>
                    <div class="feature-box">
                      <v-img
                        :src="icons.search"
                        width="32"
                        height="32"
                        class="mb-2"
                      ></v-img>
                      <span>Search</span>
                    </div>
                    <div class="feature-box">
                      <v-img
                        :src="icons.shield"
                        width="32"
                        height="32"
                        class="mb-2"
                      ></v-img>
                      <span>Secure</span>
                    </div>
                    <div class="feature-box">
                      <v-img
                        :src="icons.flash"
                        width="32"
                        height="32"
                        class="mb-2"
                      ></v-img>
                      <span>Fast</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Floating Elements -->
              <div class="floating-bubble bubble-1">
                <v-img
                  :src="icons.shopping"
                  width="20"
                  height="20"
                  class="white-icon"
                ></v-img>
              </div>
              <div class="floating-bubble bubble-2">
                <v-img
                  :src="icons.tag"
                  width="20"
                  height="20"
                  class="white-icon"
                ></v-img>
              </div>
            </div>
          </div>
        </div>

        <!-- Enhanced Chat Interface with Metrics Panel -->
        <v-row v-if="loggedIn" class="fill-height chat-container">
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
                <v-img
                  :src="icons.chart"
                  width="24"
                  height="24"
                  class="mr-2"
                ></v-img>
                System Metrics
                <v-spacer></v-spacer>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  :disabled="metricsLoading"
                  @click="fetchMetrics(true)"
                >
                  <v-img :src="icons.refresh" width="18" height="18"></v-img>
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
                  <v-img
                    :src="icons.alert"
                    width="20"
                    height="20"
                    class="mr-2"
                  ></v-img>
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
                  <v-img
                    :src="icons.databaseOff"
                    width="48"
                    height="48"
                    class="mb-2"
                  ></v-img>
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
                        <v-img :src="icons.aiAvatar"></v-img>
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
                            <v-img
                              :src="icons.robot"
                              width="24"
                              height="24"
                              class="mr-2"
                            ></v-img>
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
                        <v-img :src="icons.aiAvatar"></v-img>
                      </v-avatar>
                      <v-avatar v-else size="32" color="ebay-blue">
                        <v-img :src="icons.userAvatar"></v-img>
                      </v-avatar>
                    </div>
                    <div class="message-content">
                      <div class="message-text">
                        <p v-if="!message.isProductResults && message.text">
                          {{ message.text }}
                        </p>
                        <div
                          v-else-if="!message.isProductResults"
                          class="typing-indicator-bubble"
                        >
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                        <div v-else class="product-results">
                          <div class="results-header">
                            <div class="results-text">
                              <p v-if="message.text">
                                {{ message.text }}
                              </p>
                              <div v-else class="typing-indicator-bubble">
                                <span></span>
                                <span></span>
                                <span></span>
                              </div>
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
                                  @error="handleImageError(product)"
                                >
                                  <template v-slot:placeholder>
                                    <div class="image-placeholder">
                                      <v-img
                                        :src="icons.image"
                                        width="42"
                                        height="42"
                                      ></v-img>
                                    </div>
                                  </template>
                                </v-img>
                                <div v-else class="image-placeholder">
                                  <v-img
                                    :src="icons.image"
                                    width="42"
                                    height="42"
                                  ></v-img>
                                </div>
                              </div>
                              <div class="product-content">
                                <v-tooltip
                                  v-if="product.explanation"
                                  location="top"
                                  max-width="300"
                                >
                                  <template v-slot:activator="{ props }">
                                    <v-chip
                                      v-bind="props"
                                      v-if="product.reasoning"
                                      color="purple-lighten-4"
                                      text-color="purple-darken-2"
                                      size="small"
                                      class="mb-2 font-weight-bold"
                                      label
                                    >
                                      <v-img
                                        :src="icons.sparkles"
                                        width="16"
                                        height="16"
                                        class="mr-1"
                                      ></v-img>
                                      {{ product.reasoning }}
                                    </v-chip>
                                  </template>
                                  <div class="text-caption">
                                    <strong>AI Reasoning:</strong><br />
                                    Predicted Reward:
                                    {{
                                      product.explanation.predicted_reward.toFixed(
                                        2
                                      )
                                    }}<br />
                                    Uncertainty Bonus:
                                    {{
                                      product.explanation.uncertainty_bonus.toFixed(
                                        2
                                      )
                                    }}<br />
                                    Final Score:
                                    {{
                                      product.explanation.final_score.toFixed(2)
                                    }}
                                  </div>
                                </v-tooltip>
                                <v-chip
                                  v-else-if="product.reasoning"
                                  color="purple-lighten-4"
                                  text-color="purple-darken-2"
                                  size="small"
                                  class="mb-2 font-weight-bold"
                                  label
                                >
                                  <v-img
                                    :src="icons.sparkles"
                                    width="16"
                                    height="16"
                                    class="mr-1"
                                  ></v-img>
                                  {{ product.reasoning }}
                                </v-chip>
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
                                    <v-img
                                      :src="icons.store"
                                      width="16"
                                      height="16"
                                      class="mr-1"
                                    ></v-img>
                                    <span>{{ getSellerSummary(product) }}</span>
                                  </div>
                                  <div
                                    class="product-attribute"
                                    v-if="getShippingSummary(product)"
                                  >
                                    <v-img
                                      :src="icons.truck"
                                      width="16"
                                      height="16"
                                      class="mr-1"
                                    ></v-img>
                                    <span>{{
                                      getShippingSummary(product)
                                    }}</span>
                                  </div>
                                  <div
                                    class="product-attribute"
                                    v-if="getPrimaryCategories(product).length"
                                  >
                                    <v-img
                                      :src="icons.tag"
                                      width="16"
                                      height="16"
                                      class="mr-1"
                                    ></v-img>
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
                                  @click="sendFeedback(product.itemId, 1.0)"
                                >
                                  <v-img
                                    :src="icons.externalLink"
                                    width="16"
                                    height="16"
                                    class="mr-1"
                                  ></v-img>
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
                            >
                              <template v-slot:prepend>
                                <v-img
                                  :src="icons.plus"
                                  width="16"
                                  height="16"
                                ></v-img>
                              </template>
                              Show More Results
                            </v-btn>
                          </div>

                          <!-- History Suggestions -->
                          <div
                            v-if="
                              message.suggestions &&
                              message.suggestions.length > 0
                            "
                            class="suggestions-container mt-4"
                          >
                            <div class="text-caption text-grey mb-2">
                              Based on your history:
                            </div>
                            <div class="d-flex flex-wrap gap-2">
                              <v-chip
                                v-for="(
                                  suggestion, sIdx
                                ) in message.suggestions"
                                :key="sIdx"
                                color="ebay-blue"
                                variant="outlined"
                                link
                                @click="handleSuggestionClick(suggestion)"
                              >
                                <v-img
                                  :src="icons.history"
                                  width="16"
                                  height="16"
                                  class="mr-1"
                                ></v-img>
                                {{ suggestion }}
                              </v-chip>
                            </div>
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

                <!-- Typing Indicator Removed -->
              </v-card-text>

              <!-- Modern Input Area -->
              <v-card-actions class="chat-input">
                <div class="input-container">
                  <v-btn
                    icon
                    variant="text"
                    color="ebay-yellow"
                    class="mr-2"
                    @click="showSuggestions"
                    title="Show Suggestions"
                    :disabled="isLoading"
                  >
                    <v-img
                      :src="icons.lightbulb"
                      width="24"
                      height="24"
                    ></v-img>
                  </v-btn>
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
                    <v-img :src="icons.send" width="24" height="24"></v-img>
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
import OnboardingModal from "./OnboardingModal.vue";
// import io from "socket.io-client";
// import { marked } from "marked";
// import DOMPurify from "dompurify";
// import { performAuthCheck, logoutUser } from "../services/auth";

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
      },
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
      // Voice Interface
      isListening: false,
      isMuted: false,
      recognition: null,
      speechSynthesis: window.speechSynthesis,
      selectedVoice: null,

      // Global Notification State
      snackbar: {
        show: false,
        text: "",
        color: "info",
        timeout: 4000,
        icon: null,
      },

      // Dialog States
      showHelpDialog: false,
      confirmationDialog: {
        show: false,
        title: "",
        message: "",
        action: null,
      },
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
        const msg = `We couldn't log you in. ${authReturn.error}`;
        this.authError = msg;
        this.showNotification(msg, "error");
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
    // Helper for showing notifications
    showNotification(text, type = "info") {
      const config = {
        success: { color: "success", icon: "mdi-check-circle" },
        error: { color: "error", icon: "mdi-alert-circle" },
        warning: { color: "warning", icon: "mdi-alert" },
        info: { color: "info", icon: "mdi-information" },
      };
      const style = config[type] || config.info;
      this.snackbar = {
        show: true,
        text,
        color: style.color,
        icon: style.icon,
        timeout: 4000,
      };
    },

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

      this.showNotification(`Welcome back, ${this.ebayUsername}!`, "success");
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

      // Health check removed by user request
      // const healthCheck = await appAuth.checkApiHealth();
      // if (healthCheck.status !== "ok") { ... }

      // Generate a new client ID
      this.clientId = "client_" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("authClientId", this.clientId);

      console.log("Initiating eBay sign-in with clientId:", this.clientId);

      // Redirect to eBay OAuth
      appAuth.initiateEbayLogin(this.clientId);
    },

    async logout() {
      if (this.appSessionToken) {
        try {
          await appAuth.logout(this.appSessionToken);
        } catch (e) {
          console.warn("Logout failed on server, clearing local state anyway");
        }
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

      this.showNotification("You have been logged out.", "info");
      console.log("User logged out");
    },

    confirmLogout() {
      this.confirmationDialog = {
        show: true,
        title: "Confirm Logout",
        message:
          "Are you sure you want to log out? Your current session will be ended.",
        action: this.logout,
      };
    },

    confirmResetChat() {
      this.confirmationDialog = {
        show: true,
        title: "Reset Chat",
        message:
          "Are you sure you want to clear the chat history? This cannot be undone.",
        action: this.resetChat,
      };
    },

    resetChat() {
      this.messages = [];
      this.currentQuery = "";
      this.currentOffset = 0;
      this.showNotification("Chat history has been cleared.", "success");
      // Re-add welcome message if needed, or just leave empty
      if (this.loggedIn) {
        this.showWelcomeMessage = true;
        this.simulateFirstMessageLoading();
      }
    },

    handleConfirmation() {
      if (this.confirmationDialog.action) {
        this.confirmationDialog.action();
      }
      this.confirmationDialog.show = false;
    },

    openHelp() {
      this.showHelpDialog = true;
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

      if (message) {
        this.showNotification(message, "warning");
      }
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
        this.showNotification(this.metricsError, "error");
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
        streaming: false,
        reasoningSteps: [],
        query: this.currentQuery,
        offset: 0,
      };
      this.messages.push(aiMessage);

      // Pass the index of the new message
      await this.fetchQuery(this.currentQuery, 0, this.messages.length - 1);
    },

    async loadMore(messageIndex) {
      const message = this.messages[messageIndex];
      if (!message) return;

      message.offset = (message.offset || 0) + 10;
      this.isLoadingMore = true;

      await this.fetchQuery(message.query, message.offset, messageIndex, true);

      this.isLoadingMore = false;
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

    showSuggestions() {
      this.messages.push({
        sender: "ai",
        text: "Here are some examples of what you can ask me:",
        suggestions: this.quickSuggestions,
        timestamp: this.getCurrentTimestamp(),
      });
      // Scroll to bottom
      this.$nextTick(() => {
        const container = this.$el.querySelector(".chat-history");
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },

    // Get condition color for product chips
    getPrimaryImage(product) {
      if (!product || product.imageError) {
        return null;
      }
      const sources = [
        product.image?.imageUrl,
        product.thumbnailImages?.[0]?.imageUrl,
        product.additionalImages?.[0]?.imageUrl,
      ];
      return sources.find((src) => src) || null;
    },

    handleImageError(product) {
      // Mark product as having an image error so we show the placeholder
      product.imageError = true;
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

    // --- Voice Interface Methods ---

    initSpeechRecognition() {
      if (
        "webkitSpeechRecognition" in window ||
        "SpeechRecognition" in window
      ) {
        const SpeechRecognition =
          window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = "en-US";

        this.recognition.onstart = () => {
          this.isListening = true;
        };

        this.recognition.onend = () => {
          this.isListening = false;
        };

        this.recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          this.userInput = transcript;
          // Optional: Auto-send
          // this.sendMessage();
        };

        this.recognition.onerror = (event) => {
          console.error("Speech recognition error", event.error);
          this.isListening = false;
        };
      } else {
        console.warn("Web Speech API not supported in this browser.");
      }
    },

    toggleListening() {
      if (!this.recognition) return;
      if (this.isListening) {
        this.recognition.stop();
      } else {
        this.recognition.start();
      }
    },

    toggleMute() {
      this.isMuted = !this.isMuted;
    },

    async sendFeedback(itemId, reward = 1.0) {
      if (!this.loggedIn || !this.userId) return;

      try {
        await fetch("/api/nextgen/feedback", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: this.userId,
            item_id: itemId,
            reward: reward,
            context: {
              query: this.currentQuery,
              timestamp: new Date().toISOString(),
            },
          }),
        });
        console.log(`Feedback sent for item ${itemId}`);
      } catch (error) {
        console.error("Error sending feedback:", error);
      }
    },

    handleSuggestionClick(suggestion) {
      this.sendFeedback(`suggestion:${suggestion}`, 1.0);
      this.userInput = suggestion;
      this.sendMessage();
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const chatContainer = this.$el.querySelector(".chat-container");
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      });
    },
    // Unified fetchQuery method for initial search and pagination
    async fetchQuery(query, offset = 0, messageIndex, isLoadMore = false) {
      this.isStreaming = true;
      // Ensure we are working with the reactive message from the array
      const messageObject = this.messages[messageIndex];
      if (!messageObject) {
        console.error("Message not found at index:", messageIndex);
        return;
      }

      try {
        // Extract recent user history (last 3 messages)
        const history = this.messages
          .filter(
            (msg) => msg.sender === "user" && msg.text && msg.text !== query
          )
          .slice(-3)
          .map((msg) => msg.text);

        const requestBody = {
          query: query,
          history: history,
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

        const data = await response.json();

        if (data.error) {
          throw new Error(data.error);
        }

        // Update message with results
        if (isLoadMore) {
          // Append new products to the existing list
          if (data.items && data.items.length > 0) {
            messageObject.products.push(...data.items);
            // Update visibleCount to show the newly fetched items
            const currentVisible =
              messageObject.visibleCount ?? this.resultsPageSize;
            messageObject.visibleCount = currentVisible + data.items.length;
          }
          // Update "Show More" visibility
          if (!data.items || data.items.length < 10) {
            this.hasMoreResults = false;
          }
        } else {
          // Initial response: set all fields
          console.log("FetchQuery Data:", data);
          const answerText =
            data.answer && data.answer.trim()
              ? data.answer
              : "I found these results for you.";
          console.log("Setting answer text to:", answerText);

          // Direct assignment to reactive property
          messageObject.text = answerText;
          messageObject.products = data.items || [];
          messageObject.isProductResults = messageObject.products.length > 0;
          messageObject.entitiesSummary = this.buildEntitySummary(
            data.entities
          );
          messageObject.citations = data.citations;
          messageObject.reasoningSteps = data.reasoning_steps || [];
          messageObject.suggestions = data.suggestions || [];

          console.log(
            "Updated messageObject:",
            JSON.parse(JSON.stringify(messageObject))
          );

          // Check if we should show "Show More" button
          if (messageObject.products.length < 10) {
            this.hasMoreResults = false;
          }
        }
      } catch (error) {
        console.error("Query error:", error);
        messageObject.text += `\n[Error: ${error.message}]`;
        messageObject.isError = true;
      } finally {
        this.isStreaming = false;
        this.isTyping = false;
        this.isLoading = false;
        this.isLoadingMore = false;
        messageObject.streaming = false;

        // Ensure UI updates
        this.$nextTick(() => {
          this.scrollToBottom();
        });
      }
    },
  },
};
</script>

<style>
/* Import global chat styles */
@import "../assets/chat-layout.css";
</style>
