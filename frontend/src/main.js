/* eslint-disable prettier/prettier */
import { createApp } from "vue";
import App from "./App.vue";
import vuetify from "./plugins/vuetify"; // Import Vuetify
import { loadFonts } from "./plugins/webfontloader"; // Optional: Load fonts
import "./assets/tailwind.css"; // Import Tailwind CSS
import "./assets/boxstyles.css";
import "./assets/ebay-theme.css"; // Import eBay Theme

loadFonts(); // Optional: Load fonts

createApp(App)
  .use(vuetify) // Use Vuetify
  .mount("#app");
