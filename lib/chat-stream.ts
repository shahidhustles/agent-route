/** Decode SSE without depending on network chunk boundaries. */
export async function* sse(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error ?? `The backend returned HTTP ${response.status}.`);
  }
  if (!response.body) throw new Error("The backend returned an empty stream.");
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += (value ?? "").replace(/\r/g, "");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");
        if (data && data !== "[DONE]") {
          const event: unknown = JSON.parse(data);
          yield event;
        }
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}
