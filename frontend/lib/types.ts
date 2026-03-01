import { z } from "zod/v4";

// --- Zod schemas mirroring backend Pydantic models ---

export const DebugInfoSchema = z.object({
  classification_reasoning: z.string(),
  nodes_visited: z.array(z.string()),
  tool_calls: z.array(z.record(z.string(), z.unknown())),
  cookware_analysis: z.string().nullable().optional(),
});

export const ChatResponseSchema = z.object({
  answer: z.string(),
  query_type: z.string(),
  tools_used: z.array(z.string()).optional().default([]),
  cookware_sufficient: z.boolean().nullable().optional(),
  missing_cookware: z.array(z.string()).optional().default([]),
  debug: DebugInfoSchema.nullable().optional(),
});

export type ChatResponse = z.infer<typeof ChatResponseSchema>;

// --- SSE event types ---

export const SSEEventSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("node_start"),
    node: z.string(),
  }),
  z.object({
    type: z.literal("node_end"),
    node: z.string(),
    result: z.string().optional(),
  }),
  z.object({
    type: z.literal("token"),
    content: z.string(),
  }),
  z.object({
    type: z.literal("tool_call"),
    tool: z.string(),
    query: z.string().optional(),
  }),
  z.object({
    type: z.literal("done"),
    metadata: z.record(z.string(), z.unknown()).optional(),
  }),
  z.object({
    type: z.literal("error"),
    message: z.string(),
  }),
]);

export type SSEEvent = z.infer<typeof SSEEventSchema>;

// --- Frontend message type ---

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    queryType: string;
    toolsUsed: string[];
    cookwareSufficient?: boolean;
    missingCookware?: string[];
  };
  isStreaming?: boolean;
};
