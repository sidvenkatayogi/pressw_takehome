"use client";

import { useCallback } from "react";
import Markdown from "react-markdown";
import { Card } from "@/components/ui/card";
import type { Message } from "@/lib/types";
import { LoadingIndicator } from "./LoadingIndicator";

function DownloadButton({ content }: { content: string }) {
  const handleDownload = useCallback(() => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "recipe.txt";
    a.click();
    URL.revokeObjectURL(url);
  }, [content]);

  return (
    <button
      onClick={handleDownload}
      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-200 hover:text-slate-700 transition-colors cursor-pointer"
    >
      Download .txt
    </button>
  );
}

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

  const isRecipe = message.metadata?.queryType !== "off_topic" && message.metadata?.queryType !== "unknown";
  const showFooter = !message.isStreaming && isRecipe && message.content;

  return (
    <div className="flex justify-start">
      <Card className="max-w-[80%] rounded-2xl rounded-bl-sm border-slate-200 bg-white px-4 py-2.5 shadow-sm">
        {message.isStreaming && !message.content ? (
          <LoadingIndicator message={message.statusMessage} />
        ) : (
          <div className="markdown-body max-w-none text-sm text-slate-700">
            <Markdown>{message.content}</Markdown>
          </div>
        )}
        {showFooter && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2">
            {message.metadata?.toolsUsed && message.metadata.toolsUsed.length > 0 && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                Search used
              </span>
            )}
            {message.metadata?.cookwareSufficient === false && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-600">
                Missing: {message.metadata.missingCookware?.join(", ") || "some cookware"}
              </span>
            )}
            {message.metadata?.cookwareSufficient === true && (
              <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-600">
                Cookware OK
              </span>
            )}
            <DownloadButton content={message.content} />
          </div>
        )}
      </Card>
    </div>
  );
}
