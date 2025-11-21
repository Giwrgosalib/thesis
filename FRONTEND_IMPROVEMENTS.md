# Frontend Improvement Plan

## Goal

Enhance the user experience (UX) and user interface (UI) of the eBay AI Chatbot to match the sophistication of the "Next-Gen" backend.

## Proposed Improvements

### 1. ⚡ Streaming Responses (High Impact)

- **Current State**: The user waits for the entire backend process (NER + Search + RAG) to finish before seeing any text. This can feel slow (3-5 seconds).
- **Improvement**: Implement **Server-Sent Events (SSE)** or chunked responses.
  - Show the "Thinking..." steps: "Extracting entities...", "Searching eBay...", "Ranking results...".
  - Stream the final answer token-by-token (like ChatGPT).
- **Why**: Makes the app feel instant and "alive".

### 2. 🎨 UI Polish & Visuals

- **Product Cards**:
  - Add a "Compare" feature to select two products and see them side-by-side.
  - Add a "Price History" sparkline (simulated) to the product card.
- **Typing Indicators**:
  - Replace the generic spinner with a custom animation (e.g., bouncing dots or a robot thinking).
- **Dark Mode**:
  - Ensure high contrast in dark mode (some gray text might be hard to read).

### 3. ♿ Accessibility (A11y)

- **ARIA Labels**: Add `aria-label` to all icon-only buttons (e.g., the microphone button, send button).
- **Keyboard Nav**: Ensure the user can tab through the product results and hit Enter to open the eBay link.

### 4. 📱 Mobile Responsiveness

- **Chat Interface**: On mobile, the chat input should stick to the bottom above the keyboard.
- **Metrics Panel**: Should become a drawer or a bottom sheet on mobile instead of a side column.

### 5. 🎙️ Voice Interface (Already Planned)

- **Speech-to-Text**: Allow users to speak their query.
- **Text-to-Speech**: Read the AI's answer aloud.

## Implementation Strategy

We should prioritize **Streaming Responses** and **Voice Interface** as they provide the biggest "wow" factor for a thesis demonstration.

## Verification Plan

- **Manual Testing**:
  - Verify streaming text appears smoothly without layout shifts.
  - Test voice input in Chrome/Edge.
  - Check mobile layout using browser DevTools device toolbar.
