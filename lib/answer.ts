import { OUTCOME_ROUTER, PROVIDER_MODEL_IDS, type ModelSlug } from "../profiles";
import { createOutcomeRouter } from "../runtime";

const BACKEND = process.env.ROUTER_BACKEND_URL ?? "http://127.0.0.1:8765";
const FALLBACK = PROVIDER_MODEL_IDS[OUTCOME_ROUTER.fallback as ModelSlug] as string;

export type Preference = "cheap" | "balanced" | "fast" | "accurate";

/** The Modal model router picks the model, then the backend makes one Command Code call. */
export async function routeAnswer(text: string, preference: Preference = "balanced") {
  let router = null;
  let routerError: string | undefined;
  let model = FALLBACK;
  const { MODAL_ROUTER_URL, MODAL_PROXY_TOKEN_ID, MODAL_PROXY_TOKEN_SECRET } = process.env;
  try {
    if (!MODAL_ROUTER_URL || !MODAL_PROXY_TOKEN_ID || !MODAL_PROXY_TOKEN_SECRET)
      throw new Error("Modal router is not configured (MODAL_* in .env.modal)");
    const route = createOutcomeRouter({
      url: MODAL_ROUTER_URL,
      tokenId: MODAL_PROXY_TOKEN_ID,
      tokenSecret: MODAL_PROXY_TOKEN_SECRET,
    });
    router = await route({ user_task: text, preference });
    model = PROVIDER_MODEL_IDS[router.model_slug as ModelSlug] ?? FALLBACK;
  } catch (error) {
    routerError = `${error instanceof Error ? error.message : String(error)}; used ${FALLBACK}`;
  }

  return { model, router, routerError };
}

export async function answer(text: string, preference: Preference = "balanced") {
  const { model, router, routerError } = await routeAnswer(text, preference);
  const response = await fetch(`${BACKEND}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, model }),
  });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body, router, routerError };
}
