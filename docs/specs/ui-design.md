# Relay chat UI

Relay is a chat app built on assistant-ui 0.15 and AI SDK 7. The main job is to send a prompt and read the answer or inspect the generated artifact.

## Layout and type

Use Inter, a white canvas, near-black text, and a #f9f9f9 sidebar. Navigation stays quiet. The centered entry composer is the main action. Conversation text uses 15px type with generous line spacing, rounded grey user bubbles, and unboxed assistant replies. Buttons use stock shadcn proportions. No serif type, uppercase mono controls, cream background, or blue run-log panel.

The desktop sidebar is 244px. The conversation column is at most 800px including 32px gutters. With an artifact open, the remaining canvas splits between conversation and preview. Below 768px navigation folds into a drawer and the artifact fills the screen with an explicit Close control.

## Composer

Agent mode starts off. Balanced is the default routing preference; Cheap, Fast, and Accurate are also available. Both choices travel with every send. The plus button attaches CSV files, validates the header, rows, parse errors, and size, and enables Agent mode. An attachment chip can remove the file. Reruns reuse the backend's stored CSV.

## Conversation state

`useChatRuntime` with `AssistantChatTransport` owns messages, run state, tool calls, and reply metadata. `/api/chat` is the only send endpoint. Plain chat forwards conversation text to the model router and backend streaming endpoint. The thinking indicator remains until the first provider token, including Modal startup. The backend proxy settles provider usage after draining the stream, including when the browser disconnects.

Agent sends route and immediately start a backend run. SSE events become ordered tool calls inside the assistant reply. The tool group starts expanded. The newest step shimmers until the next event or completion. Final text follows the group. Cancellation asks the backend to stop the run container. In-flight provider spend still settles.

Routing metadata is hidden behind the reply information button. Its dialog contains votes, runner-up, all four mode picks, model estimates and sample counts, matching past runs, actual time and cost, and agent/model overrides for reruns. Quiet thumbs record passed or failed outcomes. Status errors appear inside the chat, with a small connection notice while the backend is down.

## Artifacts and navigation

All eight artifact types use the existing ArtifactView and block renderers. A reply card opens the preview again. Recorded artifacts are available in a sidebar library with no model calls. Conversations use assistant-ui's local thread list, without Assistant Cloud. This list is session-local.

## Account

Clerk signs users in with Google. Signed-out visitors see a centered card with a Continue with Google button on the white canvas. The sidebar footer shows the signed-in user's avatar, full name and email, truncated to one line each, with a Sign out row under them in the nav-button style. The footer is the same in the phone drawer. Without Clerk keys the page shows a setup message and the API routes answer 503.

## Accessibility and verification

Every icon button has a name. Dialogs trap focus and close with Escape. Keyboard focus has a visible outline. Reduced motion disables shimmer, animation, and smooth scrolling. At phone widths the page has no horizontal overflow and the artifact has its own scrolling region.

The design follows the achromatic app direction. The explicit ChatGPT reference takes precedence over the style library's dashboard patterns. The app's distinct interaction is its agent tool group plus artifact split. Test evidence and screenshots live in docs/testing.
