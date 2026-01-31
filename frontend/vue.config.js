const { defineConfig } = require("@vue/cli-service");
module.exports = defineConfig({
  transpileDependencies: true,

  pluginOptions: {
    vuetify: {
      // https://github.com/vuetifyjs/vuetify-loader/tree/next/packages/vuetify-loader
    },
  },

  devServer: {
    allowedHosts: "all",
    client: {
      webSocketURL: "auto://0.0.0.0:0/ws",
    },
    proxy: {
      "^/api": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
      "^/auth": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
      "^/health": {
        target: "http://backend:5000",
        changeOrigin: true,
      },
    },
  },
});
