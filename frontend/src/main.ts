import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";

import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/App.vue";
import { setAuthenticationFailureHandler } from "@/api/client";
import { i18n } from "@/i18n";
import { createAppRouter } from "@/router";
import { useAuthStore } from "@/stores/auth";
import "@/styles/main.scss";

const app = createApp(App);
const pinia = createPinia();
const router = createAppRouter(pinia);

app.use(pinia);
app.use(router);
app.use(i18n);
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
app.use(VueQueryPlugin, { queryClient });
window.addEventListener("tradefog:session-ended", () => queryClient.clear());

const auth = useAuthStore(pinia);
setAuthenticationFailureHandler(() => {
  auth.signOut();
  void router.replace("/login");
});
document.documentElement.lang = i18n.global.locale.value;

app.mount("#app");
