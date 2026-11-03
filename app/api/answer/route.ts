import { answer, type Preference } from "@/lib/answer";

export const maxDuration = 300;

/** "Just answer": one routed Command Code call. */
export async function POST(request: Request) {
  const { text, preference } = (await request.json()) as { text?: string; preference?: Preference };
  if (!text?.trim()) return Response.json({ error: "text is required" }, { status: 400 });

  const { ok, status, body, router, routerError } = await answer(text, preference);
  if (!ok) return Response.json(body, { status });
  return Response.json({ ...body, router, router_error: routerError });
}
