import AssistantMessageBody from "./AssistantMessageBody";
import { parseAssistantPayload } from "@/lib/assistantContent";
import type { ChatMessage } from "@/lib/types";

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const structured =
    !isUser ? parseAssistantPayload(message.content) : null;

  const time = new Date(message.created_at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-emerald-700 flex items-center justify-center text-[11px] font-bold text-white shrink-0 mr-2.5 mt-0.5">
          AI
        </div>
      )}

      <div
        className={`flex flex-col ${isUser ? "max-w-[72%] items-end" : "max-w-[min(92%,42rem)] items-start"}`}
      >
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words ${
            isUser
              ? "bg-indigo-600 text-white rounded-br-sm whitespace-pre-wrap"
              : "bg-zinc-800 text-zinc-100 rounded-bl-sm"
          }`}
        >
          {isUser ? (
            message.content
          ) : structured ? (
            <AssistantMessageBody blocks={structured.blocks} />
          ) : (
            <span className="whitespace-pre-wrap text-zinc-200">
              {message.content}
            </span>
          )}
        </div>
        <span className="text-[11px] text-zinc-600 mt-1 px-1">{time}</span>
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-full bg-indigo-800 flex items-center justify-center text-[11px] font-bold text-white shrink-0 ml-2.5 mt-0.5">
          U
        </div>
      )}
    </div>
  );
}
