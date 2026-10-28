import { ref } from "vue";

/**
 * Whether the current page is public (the property inspection walkthrough:
 * anyone with the link, no login). Kept in its own tiny module so the API
 * client can read it without importing the router (which imports every view).
 * On a public page a 401 from a logged-in-only call never sends the visitor
 * to the login screen or opens the app-key gate: the page just shows less.
 */
export const isOnPublicRoute = ref(false);
