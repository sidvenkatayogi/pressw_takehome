"use client";

import { useCallback, useReducer } from "react";
import { sendChatStream } from "@/lib/api";
import type { Message, SSEEvent } from "@/lib/types";

const NODE_LABELS: Record<string, string> = {
  classify_query: "Understanding your question...",
  research_agent: "Researching recipes...",
  cookware_check: "Checking your cookware...",
  generate_response: "Writing response...",
  refuse_response: "Composing response...",
};

type State = {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
};

type Action =
  | { type: "ADD_USER_MESSAGE"; message: Message }
  | { type: "ADD_ASSISTANT_PLACEHOLDER"; id: string }
  | { type: "APPEND_TOKEN"; id: string; content: string }
  | { type: "SET_STATUS"; id: string; statusMessage: string }
  | {
      type: "FINALIZE_ASSISTANT";
      id: string;
      metadata?: Message["metadata"];
    }
  | { type: "SET_LOADING"; isLoading: boolean }
  | { type: "SET_ERROR"; error: string | null };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [...state.messages, action.message],
        error: null,
      };
    case "ADD_ASSISTANT_PLACEHOLDER":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: action.id,
            role: "assistant",
            content: "",
            isStreaming: true,
            statusMessage: "Thinking...",
          },
        ],
      };
    case "SET_STATUS":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.id
            ? { ...m, statusMessage: action.statusMessage }
            : m
        ),
      };
    case "APPEND_TOKEN":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.id
            ? { ...m, content: m.content + action.content, statusMessage: undefined }
            : m
        ),
      };
    case "FINALIZE_ASSISTANT":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.id
            ? { ...m, isStreaming: false, statusMessage: undefined, metadata: action.metadata }
            : m
        ),
      };
    case "SET_LOADING":
      return { ...state, isLoading: action.isLoading };
    case "SET_ERROR":
      return { ...state, error: action.error, isLoading: false };
    default:
      return state;
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(reducer, {
    messages: [],
    isLoading: false,
    error: null,
  });

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || state.isLoading) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: content.trim(),
      };

      dispatch({ type: "ADD_USER_MESSAGE", message: userMsg });
      dispatch({ type: "SET_LOADING", isLoading: true });

      const assistantId = crypto.randomUUID();
      dispatch({ type: "ADD_ASSISTANT_PLACEHOLDER", id: assistantId });

      const payload = [...state.messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        let metadata: Message["metadata"] | undefined;

        await sendChatStream(payload, (event: SSEEvent) => {
          switch (event.type) {
            case "node_start": {
              const label = NODE_LABELS[event.node] || `Processing...`;
              dispatch({
                type: "SET_STATUS",
                id: assistantId,
                statusMessage: label,
              });
              break;
            }
            case "tool_call":
              dispatch({
                type: "SET_STATUS",
                id: assistantId,
                statusMessage: "Searching the web...",
              });
              break;
            case "token":
              dispatch({
                type: "APPEND_TOKEN",
                id: assistantId,
                content: event.content,
              });
              break;
            case "done": {
              const meta = event.metadata as Record<string, unknown>;
              if (meta) {
                metadata = {
                  queryType: (meta.query_type as string) || "unknown",
                  toolsUsed: (meta.tools_used as string[]) || [],
                  cookwareSufficient: meta.cookware_sufficient as
                    | boolean
                    | undefined,
                  missingCookware: meta.missing_cookware as
                    | string[]
                    | undefined,
                };
              }
              break;
            }
            case "error":
              dispatch({
                type: "SET_ERROR",
                error: event.message,
              });
              break;
          }
        });

        dispatch({
          type: "FINALIZE_ASSISTANT",
          id: assistantId,
          metadata,
        });
        dispatch({ type: "SET_LOADING", isLoading: false });
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          error:
            err instanceof Error ? err.message : "Something went wrong",
        });
      }
    },
    [state.messages, state.isLoading]
  );

  return {
    messages: state.messages,
    sendMessage,
    isLoading: state.isLoading,
    error: state.error,
  };
}
