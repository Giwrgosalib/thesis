<template>
  <v-dialog v-model="dialog" persistent max_width="600px">
    <v-card class="onboarding-card">
      <v-card-title class="text-h5 text-center pt-6">
        Welcome! Let's personalize your experience. 🚀
      </v-card-title>
      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <div class="text-subtitle-1 mb-2">What brands do you like?</div>
              <v-chip-group
                v-model="selectedBrands"
                multiple
                column
                active-class="primary--text"
              >
                <v-chip
                  v-for="brand in brands"
                  :key="brand"
                  filter
                  variant="outlined"
                  color="ebay-blue"
                >
                  {{ brand }}
                </v-chip>
              </v-chip-group>
            </v-col>
            <v-col cols="12">
              <div class="text-subtitle-1 mb-2">
                What are you interested in?
              </div>
              <v-chip-group
                v-model="selectedCategories"
                multiple
                column
                active-class="primary--text"
              >
                <v-chip
                  v-for="cat in categories"
                  :key="cat"
                  filter
                  variant="outlined"
                  color="ebay-blue"
                >
                  {{ cat }}
                </v-chip>
              </v-chip-group>
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="grey" variant="text" @click="skip">Skip</v-btn>
        <v-btn color="ebay-blue" variant="flat" @click="save"
          >Start Exploring</v-btn
        >
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
  name: "OnboardingModal",
  props: {
    userId: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      dialog: false,
      brands: [
        "Nike",
        "Adidas",
        "Apple",
        "Sony",
        "Samsung",
        "Gucci",
        "Rolex",
        "Lego",
      ],
      categories: [
        "Sneakers",
        "Electronics",
        "Watches",
        "Toys",
        "Fashion",
        "Collectibles",
      ],
      selectedBrands: [], // Indices
      selectedCategories: [], // Indices
    };
  },
  mounted() {
    // Check if user has already onboarded
    const hasOnboarded = localStorage.getItem("hasOnboarded");
    if (!hasOnboarded) {
      this.dialog = true;
    }
  },
  methods: {
    skip() {
      localStorage.setItem("hasOnboarded", "true");
      this.dialog = false;
    },
    async save() {
      // Map indices to values
      const brands = this.selectedBrands.map((i) => this.brands[i]);
      const categories = this.selectedCategories.map((i) => this.categories[i]);

      try {
        await fetch("/api/nextgen/preferences", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: this.userId,
            preferences: {
              brands: brands,
              categories: categories,
            },
          }),
        });
        console.log("Preferences saved");
      } catch (e) {
        console.error("Failed to save preferences", e);
      }

      localStorage.setItem("hasOnboarded", "true");
      this.dialog = false;
      this.$emit("onboarded");
    },
  },
};
</script>

<style scoped>
.onboarding-card {
  border-radius: 16px;
}
</style>
