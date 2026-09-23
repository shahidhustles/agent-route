import {
  convertToModelMessages,
  createGateway,
  createUIMessageStream,
  createUIMessageStreamResponse,
  streamText,
  toUIMessageStream,
  type UIMessage,
} from "ai";

import { latestUserText, routeTask } from "@/lib/routing";

export const maxDuration = 180;

type RouterUIMessage = UIMessage<
  never,
  {
    routing: {
      status: "routing" | "selected";
      model?: string;
      confidence?: number;
    };
  }
>;

export async function POST(request: Request) {
  const apiKey = process.env.AI_GATEWAY_API_KEY;
  if (!apiKey) {
    return Response.json({ error: "AI Gateway is not configured." }, { status: 500 });
  }

  const { messages }: { messages: RouterUIMessage[] } = await request.json();
  const task = latestUserText(messages);
  const gateway = createGateway({ apiKey });

  const stream = createUIMessageStream<RouterUIMessage>({
    originalMessages: messages,
    execute: async ({ writer }) => {
      writer.write({ type: "start" });
      writer.write({
        type: "data-routing",
        id: "routing-status",
        data: { status: "routing" },
      });

      const selection = await routeTask(task);

      writer.write({
        type: "data-routing",
        id: "routing-status",
        data: {
          status: "selected",
          model: selection.model_slug,
          confidence: selection.confidence,
        },
      });

      const result = streamText({
        model: gateway("inclusionai/ling-3.0-flash-fin-free"),
        system:
          "You are a concise, capable assistant. Answer the user's task directly. Use Markdown when it improves readability.",
        messages: await convertToModelMessages(messages),
      });

      writer.merge(
        toUIMessageStream({
          stream: result.stream,
          sendStart: false,
          onError: () => "The response could not be generated. Please try again.",
        }),
      );
    },
    onError: (error) => (error instanceof Error ? error.message : "The request failed."),
  });

  return createUIMessageStreamResponse({ stream });
}
