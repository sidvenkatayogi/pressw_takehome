import Markdown from "react-markdown";
import { Card } from "@/components/ui/card";
import type { Message } from "@/lib/types";
import { LoadingIndicator } from "./LoadingIndicator";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-orange-500 px-4 py-2.5 text-white">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <Card className="max-w-[80%] rounded-2xl rounded-bl-sm border-slate-200 bg-white px-4 py-2.5 shadow-sm">
        {message.isStreaming && !message.content ? (
          <LoadingIndicator />
        ) : (
          <div className="prose prose-sm prose-slate max-w-none text-sm leading-relaxed">
            <Markdown>{message.content}</Markdown>
          </div>
        )}
        {message.metadata && !message.isStreaming && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-slate-100 pt-2">
            {message.metadata.toolsUsed.length > 0 && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                Search used
              </span>
            )}
            {message.metadata.cookwareSufficient === false && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-600">
                Missing: {message.metadata.missingCookware?.join(", ") || "some cookware"}
              </span>
            )}
            {message.metadata.cookwareSufficient === true && (
              <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-600">
                Cookware OK
              </span>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
